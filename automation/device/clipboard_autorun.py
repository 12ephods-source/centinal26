from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

MARKER = "# FROST-AUTORUN:1"
DEFAULT_ROOT = Path.home() / ".local" / "share" / "frost-clipboard-autorun"
MAX_BYTES = int(os.environ.get("FROST_CLIPBOARD_MAX_BYTES", "262144"))
REPLAY_WINDOW_SECONDS = float(
    os.environ.get("FROST_CLIPBOARD_REPLAY_WINDOW", "2.0")
)
TERMUX_BASH = Path("/data/data/com.termux/files/usr/bin/bash")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def canonical_input(raw: str) -> tuple[str, str]:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip("\n")
    lines = stripped.splitlines()
    first_index = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first_index is None:
        raise ValueError("clipboard is empty")
    marker = lines[first_index].strip()
    if marker != MARKER and not marker.startswith(MARKER + " "):
        raise ValueError("clipboard text is not marked for Frost autorun")
    shell = "bash"
    if "shell=python" in marker or "lang=python" in marker:
        shell = "python"
    elif "shell=bash" in marker or "lang=bash" in marker:
        shell = "bash"
    body_lines = lines[:first_index] + lines[first_index + 1 :]
    body = "\n".join(body_lines).strip("\n") + "\n"
    if not body.strip():
        raise ValueError("marked clipboard contains no executable body")
    if "\x00" in body:
        raise ValueError("NUL byte rejected")
    return shell, body


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def root_path() -> Path:
    root = Path(
        os.environ.get("FROST_CLIPBOARD_STATE_ROOT", str(DEFAULT_ROOT))
    ).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    (root / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "runs").mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root


def bash_path() -> str:
    if TERMUX_BASH.is_file():
        return str(TERMUX_BASH)
    resolved = shutil.which("bash")
    if resolved:
        return resolved
    raise RuntimeError("bash executable unavailable")


def ignored(reason: str, *, digest: str | None = None) -> int:
    value = {"status": "IGNORED", "reason": reason}
    if digest:
        value["sha256"] = digest
    print(json.dumps(value, sort_keys=True))
    print("FROST_AUTORUN_IGNORED")
    return 0


def stage(raw: str, root: Path) -> int:
    if len(raw.encode("utf-8")) > MAX_BYTES:
        return ignored("clipboard_too_large")
    try:
        shell, body = canonical_input(raw)
    except ValueError as exc:
        return ignored(str(exc))

    digest = sha256_text(body)
    replay_path = root / "last_event.json"
    previous = read_state(replay_path)
    now = time.time()
    if (
        previous.get("sha256") == digest
        and now - float(previous.get("time", 0)) < REPLAY_WINDOW_SECONDS
    ):
        return ignored("duplicate_clipboard_event", digest=digest)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    suffix = ".py" if shell == "python" else ".sh"
    script_path = root / "inbox" / f"{stamp}-{digest[:16]}{suffix}"
    raw_path = root / "inbox" / f"{stamp}-{digest[:16]}.clipboard.txt"
    raw_path.write_text(raw, encoding="utf-8")
    script_path.write_text(body, encoding="utf-8")
    os.chmod(raw_path, 0o600)
    os.chmod(script_path, 0o700)

    pending = {
        "schema": "frost.clipboard_autorun.pending.v1",
        "status": "STAGED",
        "staged_at": now_iso(),
        "sha256": digest,
        "shell": shell,
        "script_path": str(script_path),
        "raw_clipboard_path": str(raw_path),
        "raw_clipboard_sha256": sha256_file(raw_path),
    }
    write_json(root / "pending.json", pending)
    write_json(
        replay_path,
        {"sha256": digest, "time": now, "captured_at": now_iso()},
    )
    print(json.dumps(pending, indent=2, sort_keys=True))
    print("FROST_AUTORUN_STAGED")
    return 0


def _resolve_pending_script(root: Path, pending: dict) -> tuple[Path, str, str]:
    script_path = Path(str(pending.get("script_path", ""))).expanduser()
    shell = str(pending.get("shell", ""))
    digest = str(pending.get("sha256", ""))
    inbox = (root / "inbox").resolve()
    try:
        resolved = script_path.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError("staged script is unavailable") from exc
    if resolved.parent != inbox:
        raise RuntimeError("staged script escaped the autorun inbox")
    if not resolved.is_file() or resolved.is_symlink():
        raise RuntimeError("staged script is not a regular file")
    if shell not in {"bash", "python"}:
        raise RuntimeError("unsupported staged interpreter")
    if len(digest) != 64 or sha256_file(resolved) != digest:
        raise RuntimeError("staged script SHA-256 mismatch")
    return resolved, shell, digest


def run_pending(root: Path) -> int:
    pending_path = root / "pending.json"
    if not pending_path.is_file():
        return ignored("no_staged_script")

    running_path = root / f"running-{os.getpid()}.json"
    try:
        pending_path.replace(running_path)
    except FileNotFoundError:
        return ignored("no_staged_script")
    pending = read_state(running_path)

    try:
        script_path, shell, digest = _resolve_pending_script(root, pending)
    except RuntimeError as exc:
        failure = {
            "schema": "frost.clipboard_autorun.receipt.v1",
            "captured_at": now_iso(),
            "status": "REJECTED",
            "reason": str(exc),
            "promotion_performed": False,
        }
        write_json(root / "runs" / f"rejected-{os.getpid()}.json", failure)
        running_path.unlink(missing_ok=True)
        print(json.dumps(failure, indent=2, sort_keys=True))
        return 2

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    log_path = root / "runs" / f"{stamp}-{digest[:16]}.log"
    receipt_path = root / "runs" / f"{stamp}-{digest[:16]}.json"
    command = (
        [sys.executable, str(script_path)]
        if shell == "python"
        else [bash_path(), str(script_path)]
    )

    print(f"FROST AUTORUN: {script_path.name}")
    print(f"SHA256: {digest}")
    print("--- script ---")
    print(script_path.read_text(encoding="utf-8"), end="")
    print("--- execution ---")
    started = time.time()
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    output = (completed.stdout or "") + (completed.stderr or "")
    log_path.write_text(output, encoding="utf-8")
    os.chmod(log_path, 0o600)
    receipt = {
        "schema": "frost.clipboard_autorun.receipt.v1",
        "captured_at": now_iso(),
        "status": "EXECUTED",
        "sha256": digest,
        "shell": shell,
        "script_path": str(script_path),
        "log_path": str(log_path),
        "exit_code": completed.returncode,
        "duration_seconds": round(time.time() - started, 6),
        "autorun_marker_required": True,
        "promotion_performed": False,
    }
    write_json(receipt_path, receipt)
    running_path.unlink(missing_ok=True)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Marked clipboard-to-Termux autorun bridge")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--stage", action="store_true")
    mode.add_argument("--run-pending", action="store_true")
    mode.add_argument("--direct", action="store_true")
    args = parser.parse_args()
    root = root_path()

    if args.stage:
        return stage(sys.stdin.read(), root)
    if args.run_pending:
        return run_pending(root)
    raw = sys.stdin.read()
    staged = stage(raw, root)
    if staged != 0 or not (root / "pending.json").is_file():
        return staged
    return run_pending(root)


if __name__ == "__main__":
    raise SystemExit(main())
