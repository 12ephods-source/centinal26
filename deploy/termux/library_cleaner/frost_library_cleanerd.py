"""Fail-closed Termux daemon for reclaiming ChatGPT Library upload slots.

The cleaner uses the already-authenticated Library web UI through Android
UIAutomator/ADB. It never calls private provider endpoints. A candidate is deleted
only after an exact filename match is selected, a local archive copy is hashed and
ledgered, and the same exact filename is re-identified immediately before delete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

APP_HOME = Path.home() / ".local" / "share" / "frost-library-cleaner"
CONFIG_PATH = APP_HOME / "config.json"
STATE_PATH = APP_HOME / "state.json"
LEDGER_PATH = APP_HOME / "archive-ledger.jsonl"
SNAPSHOT_DIR = APP_HOME / "ui-snapshots"

DEFAULT_CONFIG = {
    "library_url": "https://chatgpt.com/library",
    "scan_interval_seconds": 3600,
    "settle_seconds": 2.0,
    "download_timeout_seconds": 90,
    "max_deletes_per_cycle": 20,
    "auto_delete": True,
    "archive_dir": "~/storage/downloads/FrostForgeLibraryArchive",
    "download_dirs": [
        "~/storage/downloads",
        "/sdcard/Download",
        "/storage/emulated/0/Download",
    ],
    "search_queries": ["SHA256", "cleanup", "manifest"],
    "explicit_delete_names": [],
    "safe_delete_patterns": [
        r"(?i)^SHA256SUMS(?:\([^)]*\))?\.txt$",
        r"(?i)^.+\.sha256$",
        r"(?i)^FILE_LIBRARY_CLEANUP_(?:REPORT|MANIFEST)\.(?:md|json)$",
    ],
    "never_delete_patterns": [
        r"(?i)(?:^|[^a-z0-9])CURRENT(?:$|[^a-z0-9])",
        r"(?i)(?:^|[^a-z0-9])CANONICAL(?:$|[^a-z0-9])",
        r"(?i)(?:^|[^a-z0-9])PHYSICAL(?:$|[^a-z0-9]).*EVIDENCE",
        r"(?i)^device_evidence\.json$",
        r"(?i)^validation_report\.json$",
        r"(?i)^MANIFEST\.sha256\.json$",
        r"(?i).*heartbeat.*",
        r"(?i).*reboot.*evidence.*",
    ],
    "labels": {
        "search": ["Search", "Search files", "Buscar", "Buscar archivos"],
        "download": ["Download", "Descargar"],
        "delete": ["Delete", "Eliminar"],
        "confirm": ["Delete", "Eliminar", "Confirm", "Confirmar"],
    },
}

BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
FILE_RE = re.compile(
    r"(?i).+\.(?:zip|pdf|md|txt|json|csv|py|sh|js|ts|docx?|xlsx?|pptx?|png|jpe?g|webp|sha256)$"
)


@dataclass(frozen=True)
class UINode:
    text: str
    description: str
    resource_id: str
    class_name: str
    bounds: tuple[int, int, int, int]

    @property
    def label(self) -> str:
        return (self.text or self.description).strip()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, check=False, text=True, timeout=timeout)


def adb(*arguments: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return run(["adb", *arguments], timeout=timeout)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def matches_any(name: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, name) for pattern in patterns)


def is_safe_candidate(name: str, config: dict) -> bool:
    if matches_any(name, config["never_delete_patterns"]):
        return False
    if name in set(config.get("explicit_delete_names", [])):
        return True
    return matches_any(name, config["safe_delete_patterns"])


def parse_ui_xml(xml_text: str) -> list[UINode]:
    root = ET.fromstring(xml_text)
    nodes: list[UINode] = []
    for element in root.iter("node"):
        match = BOUNDS_RE.fullmatch(element.attrib.get("bounds", ""))
        if not match:
            continue
        nodes.append(
            UINode(
                text=element.attrib.get("text", ""),
                description=element.attrib.get("content-desc", ""),
                resource_id=element.attrib.get("resource-id", ""),
                class_name=element.attrib.get("class", ""),
                bounds=tuple(map(int, match.groups())),
            )
        )
    return nodes


def exact_name_nodes(nodes: list[UINode], name: str) -> list[UINode]:
    target = normalize(name)
    return [
        node
        for node in nodes
        if target in {normalize(node.text), normalize(node.description)}
    ]


def label_nodes(nodes: list[UINode], labels: list[str]) -> list[UINode]:
    wanted = {normalize(label) for label in labels}
    return [
        node
        for node in nodes
        if wanted.intersection({normalize(node.text), normalize(node.description)})
    ]


def candidate_names(nodes: list[UINode]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        for value in (node.text.strip(), node.description.strip()):
            if value and len(value) <= 240 and FILE_RE.fullmatch(value) and value not in seen:
                result.append(value)
                seen.add(value)
    return result


def load_config() -> dict:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    user = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config.update(user)
    if isinstance(user.get("labels"), dict):
        config["labels"].update(user["labels"])
    return config


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"archived": {}, "deleted": {}, "last_cycle": None}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"archived": {}, "deleted": {}, "last_cycle": None}


def save_state(state: dict) -> None:
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(STATE_PATH)


def append_ledger(record: dict) -> None:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    entry = dict(record)
    entry["entry_sha256"] = hashlib.sha256(canonical).hexdigest()
    with LEDGER_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")


def ensure_adb() -> bool:
    status = adb("get-state", timeout=8)
    return status.returncode == 0 and status.stdout.strip() == "device"


def tap(node: UINode) -> None:
    x1, y1, x2, y2 = node.bounds
    result = adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
    if result.returncode != 0:
        raise RuntimeError("ADB tap failed")


def dump_ui(tag: str) -> list[UINode]:
    remote = "/sdcard/frost_library_cleaner_ui.xml"
    dumped = adb("shell", "uiautomator", "dump", remote, timeout=15)
    if dumped.returncode != 0:
        raise RuntimeError("UIAutomator dump failed")
    pulled = adb("exec-out", "cat", remote, timeout=10)
    if pulled.returncode != 0 or not pulled.stdout.strip():
        raise RuntimeError("UIAutomator XML unavailable")
    snapshot = SNAPSHOT_DIR / f"{int(time.time())}_{tag}.xml"
    snapshot.write_text(pulled.stdout, encoding="utf-8")
    return parse_ui_xml(pulled.stdout)


def open_library(config: dict) -> None:
    opened = adb(
        "shell",
        "am",
        "start",
        "-a",
        "android.intent.action.VIEW",
        "-d",
        config["library_url"],
        timeout=15,
    )
    if opened.returncode != 0:
        raise RuntimeError("could not open Library URL")
    time.sleep(float(config["settle_seconds"]))


def search_field(nodes: list[UINode], config: dict) -> UINode:
    direct = label_nodes(nodes, config["labels"]["search"])
    if len(direct) == 1:
        return direct[0]
    candidates = [node for node in nodes if "search" in node.resource_id.casefold()]
    if len(candidates) != 1:
        raise RuntimeError("Library search control is missing or ambiguous")
    return candidates[0]


def type_query(query: str) -> None:
    adb("shell", "input", "keycombination", "META_CTRL_ON", "KEYCODE_A", timeout=10)
    adb("shell", "input", "keyevent", "KEYCODE_DEL", timeout=10)
    encoded = query.replace("%", "%25").replace(" ", "%s")
    typed = adb("shell", "input", "text", encoded, timeout=20)
    if typed.returncode != 0:
        raise RuntimeError("could not enter Library search query")
    adb("shell", "input", "keyevent", "KEYCODE_ENTER", timeout=10)


def search_library(query: str, config: dict) -> list[UINode]:
    nodes = dump_ui("before_search")
    field = search_field(nodes, config)
    tap(field)
    time.sleep(0.3)
    type_query(query)
    time.sleep(float(config["settle_seconds"]))
    return dump_ui("search_result")


def select_exact(name: str, config: dict) -> list[UINode]:
    nodes = search_library(name, config)
    exact = exact_name_nodes(nodes, name)
    if len(exact) != 1:
        raise RuntimeError(f"exact Library item is ambiguous: {name!r}")
    tap(exact[0])
    time.sleep(float(config["settle_seconds"]))
    selected = dump_ui("selected")
    if not exact_name_nodes(selected, name):
        raise RuntimeError("selected view lost exact filename identity")
    return selected


def click_unique(nodes: list[UINode], labels: list[str], action: str) -> None:
    matches = label_nodes(nodes, labels)
    if len(matches) != 1:
        raise RuntimeError(f"{action} control is missing or ambiguous")
    tap(matches[0])


def download_snapshot(config: dict) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for raw_dir in config["download_dirs"]:
        directory = Path(os.path.expanduser(raw_dir))
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.is_file():
                stat = path.stat()
                snapshot[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def wait_for_download(before: dict[str, tuple[int, int]], config: dict) -> Path | None:
    deadline = time.time() + int(config["download_timeout_seconds"])
    while time.time() < deadline:
        for raw_dir in config["download_dirs"]:
            directory = Path(os.path.expanduser(raw_dir))
            if not directory.exists():
                continue
            files = sorted(
                (path for path in directory.iterdir() if path.is_file()),
                key=lambda path: path.stat().st_mtime_ns,
                reverse=True,
            )
            for path in files:
                if path.name.endswith((".part", ".tmp", ".crdownload")):
                    continue
                stat = path.stat()
                old = before.get(str(path))
                if old is None or old != (stat.st_size, stat.st_mtime_ns):
                    size = stat.st_size
                    time.sleep(1.0)
                    if path.exists() and path.stat().st_size == size:
                        return path
        time.sleep(1.0)
    return None


def archive_download(name: str, source: Path, config: dict, state: dict) -> tuple[Path, str]:
    archive_dir = Path(os.path.expanduser(config["archive_dir"]))
    archive_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(source)
    safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)[:160]
    destination = archive_dir / f"{int(time.time())}__{digest[:12]}__{safe_name}"
    shutil.copy2(source, destination)
    if sha256_file(destination) != digest:
        raise RuntimeError("archive copy hash mismatch")
    state.setdefault("archived", {})[digest] = str(destination)
    append_ledger(
        {
            "event": "ARCHIVED_BEFORE_DELETE",
            "source_name": name,
            "archive_path": str(destination),
            "sha256": digest,
            "size": destination.stat().st_size,
            "timestamp": time.time(),
        }
    )
    return destination, digest


def archive_candidate(name: str, config: dict, state: dict) -> tuple[Path, str]:
    selected = select_exact(name, config)
    before = download_snapshot(config)
    click_unique(selected, config["labels"]["download"], "download")
    downloaded = wait_for_download(before, config)
    if downloaded is None:
        raise RuntimeError("download did not complete; refusing delete")
    return archive_download(name, downloaded, config, state)


def delete_candidate(name: str, digest: str, config: dict, state: dict) -> None:
    selected = select_exact(name, config)
    click_unique(selected, config["labels"]["delete"], "delete")
    time.sleep(float(config["settle_seconds"]))
    confirmation = dump_ui("delete_confirmation")
    if not exact_name_nodes(confirmation, name):
        raise RuntimeError("confirmation does not expose exact filename; refusing blind delete")
    click_unique(confirmation, config["labels"]["confirm"], "confirm delete")
    time.sleep(float(config["settle_seconds"]))
    if exact_name_nodes(search_library(name, config), name):
        raise RuntimeError("post-delete verification still finds Library item")
    state.setdefault("deleted", {})[name] = {"sha256": digest, "timestamp": time.time()}
    append_ledger(
        {
            "event": "LIBRARY_DELETE_VERIFIED",
            "source_name": name,
            "archive_sha256": digest,
            "timestamp": time.time(),
        }
    )


def discover_candidates(config: dict) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    queries = list(config["search_queries"]) + list(config.get("explicit_delete_names", []))
    for query in queries:
        for name in candidate_names(search_library(query, config)):
            if name not in seen and is_safe_candidate(name, config):
                result.append(name)
                seen.add(name)
    return result


def cycle(config: dict, *, dry_run: bool) -> dict:
    result = {"found": [], "archived": [], "deleted": [], "errors": []}
    state = load_state()
    if not ensure_adb():
        result["errors"].append("ADB_NOT_CONNECTED")
        return result
    open_library(config)
    candidates = discover_candidates(config)
    result["found"] = candidates
    for name in candidates[: int(config["max_deletes_per_cycle"])]:
        if name in state.get("deleted", {}):
            continue
        if dry_run or not config.get("auto_delete", True):
            continue
        try:
            archive_path, digest = archive_candidate(name, config, state)
            save_state(state)
            result["archived"].append(
                {"name": name, "path": str(archive_path), "sha256": digest}
            )
            delete_candidate(name, digest, config, state)
            save_state(state)
            result["deleted"].append({"name": name, "sha256": digest})
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            result["errors"].append({"name": name, "error": str(exc)})
            try:
                open_library(config)
            except RuntimeError:
                break
    state["last_cycle"] = {"timestamp": time.time(), "result": result}
    save_state(state)
    return result


def setup() -> int:
    load_config()
    print(f"config={CONFIG_PATH}")
    print(f"ledger={LEDGER_PATH}")
    if ensure_adb():
        print("ADB_CONNECTED")
        return 0
    print("ADB_NOT_CONNECTED")
    print("Pair Android Wireless debugging once with: adb pair <host:pair-port>")
    return 2


def status() -> int:
    state = load_state()
    print(
        json.dumps(
            {
                "adb_connected": ensure_adb(),
                "config": str(CONFIG_PATH),
                "ledger": str(LEDGER_PATH),
                "deleted_count": len(state.get("deleted", {})),
                "archived_hash_count": len(state.get("archived", {})),
                "last_cycle": state.get("last_cycle"),
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["daemon", "once", "dry-run", "setup", "status"])
    args = parser.parse_args()
    config = load_config()
    if args.command == "setup":
        return setup()
    if args.command == "status":
        return status()
    if args.command == "dry-run":
        print(json.dumps(cycle(config, dry_run=True), indent=2))
        return 0
    if args.command == "once":
        print(json.dumps(cycle(config, dry_run=False), indent=2))
        return 0
    while True:
        print(json.dumps(cycle(config, dry_run=False), sort_keys=True), flush=True)
        time.sleep(max(300, int(config["scan_interval_seconds"])))


if __name__ == "__main__":
    raise SystemExit(main())
