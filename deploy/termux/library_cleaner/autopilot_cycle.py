"""Bounded improvement loop for the Frost Forge Termux Library Cleaner.

The loop never widens deletion authority. It audits the installed cleaner, applies
only deterministic local repairs, keeps deletion disarmed on uncertainty, and
records each observe/measure/criticize/improve/verify cycle as JSONL evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import py_compile
import re
import subprocess
import time
from pathlib import Path

APP = Path.home() / ".local" / "share" / "frost-library-cleaner"
CFG = APP / "config.json"
RESULT = APP / "qualification-result.json"
LOG = APP / "autopilot-cycle.jsonl"
SERVICE = Path("/data/data/com.termux/files/usr/var/service/frost-library-cleaner")

HIGH_RISK_RULES = {
    "destructive_root_delete": re.compile(r"rm\s+-rf\s+/(?:\s|$)"),
    "filesystem_format": re.compile(r"\bmkfs(?:\.|\s)"),
    "raw_block_write": re.compile(r"\bdd\s+[^\n]*\bof=/dev/"),
    "remote_pipe_shell": re.compile(r"(?:curl|wget)[^\n|]*\|\s*(?:ba)?sh\b"),
    "reverse_shell": re.compile(r"/dev/tcp/|\bnc\s+[^\n]*\s-e\s"),
    "shell_true": re.compile(r"shell\s*=\s*True"),
}

SCAN_NAMES = (
    "frost_library_cleanerd.py",
    "package_evidence.py",
    "qualify_and_arm.sh",
    "disarm.sh",
    "autopilot_cycle.py",
)


def run(command: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config() -> dict:
    if not CFG.exists():
        return {}
    return json.loads(CFG.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    APP.mkdir(parents=True, exist_ok=True)
    temp = CFG.with_suffix(".tmp")
    temp.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(CFG)


def append_log(record: dict) -> None:
    APP.mkdir(parents=True, exist_ok=True)
    payload = dict(record)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["entry_sha256"] = hashlib.sha256(canonical).hexdigest()
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True) + "\n")


def scan_path(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    findings: list[dict[str, str]] = []
    for rule, pattern in HIGH_RISK_RULES.items():
        if pattern.search(text):
            findings.append({"file": str(path), "rule": rule})
    return findings


def static_scan() -> dict:
    findings: list[dict[str, str]] = []
    scanned: list[dict[str, str]] = []
    for name in SCAN_NAMES:
        path = APP / name
        if path.is_file():
            scanned.append({"file": str(path), "sha256": sha256(path)})
            findings.extend(scan_path(path))
    return {"scanned": scanned, "findings": findings, "pass": not findings}


def syntax_check() -> dict:
    results: list[dict[str, object]] = []
    for name in ("frost_library_cleanerd.py", "package_evidence.py", "autopilot_cycle.py"):
        path = APP / name
        if not path.is_file():
            results.append({"file": name, "pass": False, "error": "MISSING"})
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            results.append({"file": name, "pass": True})
        except py_compile.PyCompileError as exc:
            results.append({"file": name, "pass": False, "error": str(exc)})
    return {"results": results, "pass": all(item["pass"] for item in results)}


def adb_connected() -> bool:
    result = run(["adb", "get-state"], timeout=8)
    return result.returncode == 0 and result.stdout.strip() == "device"


def qualification_clean() -> bool:
    if not RESULT.is_file():
        return False
    try:
        payload = json.loads(RESULT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return not payload.get("errors")


def disarm(reason: str) -> dict:
    config = load_config()
    config["auto_delete"] = False
    config["autopilot_disarm_reason"] = reason
    config["autopilot_disarmed_at"] = time.time()
    save_config(config)
    if SERVICE.exists():
        run(["sv", "down", str(SERVICE)], timeout=10)
    return {"action": "DISARM", "reason": reason}


def ensure_local_state() -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for path in (
        APP,
        APP / "ui-snapshots",
        APP / "service-log",
        Path.home() / "storage" / "downloads" / "FrostForgeLibraryArchive",
        Path.home() / "storage" / "downloads" / "FrostForgeLibraryCleanerEvidence",
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
            actions.append({"action": "ENSURE_DIRECTORY", "path": str(path)})
        except OSError as exc:
            actions.append({"action": "DIRECTORY_BLOCKED", "path": str(path), "error": str(exc)})
    return actions


def qualify_if_possible() -> dict:
    if not adb_connected():
        return {"action": "QUALIFICATION_DEFERRED", "reason": "ADB_NOT_CONNECTED"}
    command = APP / "qualify_and_arm.sh"
    if not command.is_file():
        return {"action": "QUALIFICATION_DEFERRED", "reason": "QUALIFIER_MISSING"}
    result = run([str(command)], timeout=180)
    return {
        "action": "QUALIFICATION_ATTEMPTED",
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }


def fingerprint() -> str:
    config = load_config()
    payload = {
        "auto_delete": config.get("auto_delete", False),
        "qualification_clean": qualification_clean(),
        "adb_connected": adb_connected(),
        "files": {
            name: sha256(APP / name) if (APP / name).is_file() else None
            for name in SCAN_NAMES
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def one_cycle(index: int) -> dict:
    before = fingerprint()
    scan = static_scan()
    syntax = syntax_check()
    actions = ensure_local_state()

    if not scan["pass"]:
        actions.append(disarm("STATIC_SCAN_FAILED"))
    elif not syntax["pass"]:
        actions.append(disarm("SYNTAX_CHECK_FAILED"))
    else:
        config = load_config()
        if config.get("auto_delete") and not qualification_clean():
            actions.append(disarm("ARMED_WITHOUT_CLEAN_QUALIFICATION_RECEIPT"))
        elif not config.get("auto_delete", False):
            actions.append(qualify_if_possible())

    after = fingerprint()
    record = {
        "schema": "frost.library_cleaner.autopilot-cycle.v1",
        "cycle": index,
        "timestamp": time.time(),
        "observe": {"fingerprint_before": before, "adb_connected": adb_connected()},
        "measure": {"static_scan": scan, "syntax": syntax},
        "criticize": {
            "preferred_strategy": "visible_authenticated_ui_with_archive_before_delete",
            "rejected_strategy": "undocumented_private_provider_endpoint",
        },
        "improve": actions,
        "verify": {"fingerprint_after": after, "stable": before == after},
    }
    append_log(record)
    return record


def autopilot(cycles: int) -> list[dict]:
    records: list[dict] = []
    previous_after: str | None = None
    for index in range(1, max(1, cycles) + 1):
        record = one_cycle(index)
        records.append(record)
        current_after = record["verify"]["fingerprint_after"]
        if previous_after == current_after and record["verify"]["stable"]:
            break
        previous_after = current_after
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit", "autopilot", "scan"], nargs="?", default="autopilot")
    parser.add_argument("--cycles", type=int, default=3)
    args = parser.parse_args()

    if args.command == "scan":
        result = static_scan()
        print(json.dumps(result, indent=2))
        return 0 if result["pass"] else 2
    if args.command == "audit":
        result = one_cycle(1)
        print(json.dumps(result, indent=2))
        return 0 if result["measure"]["static_scan"]["pass"] and result["measure"]["syntax"]["pass"] else 2

    result = autopilot(args.cycles)
    print(json.dumps(result, indent=2))
    latest = result[-1]
    return 0 if latest["measure"]["static_scan"]["pass"] and latest["measure"]["syntax"]["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
