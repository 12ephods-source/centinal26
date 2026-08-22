from __future__ import annotations

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
REPLAY_WINDOW_SECONDS = float(os.environ.get("FROST_CLIPBOARD_REPLAY_WINDOW", "2.0"))
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


def bash_path() -> str:
    if TERMUX_BASH.is_file():
        return str(TERMUX_BASH)
    resolved = shutil.which("bash")
    if resolved:
        return resolved
    raise RuntimeError("bash executable unavailable")


def main() -> int:
    raw = sys.stdin.read()
    raw_bytes = raw.encode("utf-8")
    if len(raw_bytes) > MAX_BYTES:
        print(json.dumps({"status": "IGNORED", "reason": "clipboard_too_large"}))
        return 0

    root = Path(
        os.environ.get("FROST_CLIPBOARD_STATE_ROOT", str(DEFAULT_ROOT))
    ).expanduser()
    inbox = root / "inbox"
    runs = root / "runs"
    root.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    runs.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)

    try:
        shell, body = canonical_input(raw)
    except ValueError as exc:
        print(json.dumps({"status": "IGNORED", "reason": str(exc)}))
        return 0

    digest = sha256_text(body)
    replay_path = root / "last_event.json"
    previous = read_state(replay_path)
    now = time.time()
    if (
        previous.get("sha256") == digest
        and now - float(previous.get("time", 0)) < REPLAY_WINDOW_SECONDS
    ):
        print(
            json.dumps(
                {
                    "status": "IGNORED",
                    "reason": "duplicate_clipboard_event",
                    "sha256": digest,
                }
            )
        )
        return 0

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    suffix = ".py" if shell == "python" else ".sh"
    script_path = inbox / f"{stamp}-{digest[:16]}{suffix}"
    log_path = runs / f"{stamp}-{digest[:16]}.log"
    receipt_path = runs / f"{stamp}-{digest[:16]}.json"
    script_path.write_text(body, encoding="utf-8")
    os.chmod(script_path, 0o700)
    write_json(
        replay_path,
        {"sha256": digest, "time": now, "captured_at": now_iso()},
    )

    command = (
        [sys.executable, str(script_path)]
        if shell == "python"
        else [bash_path(), str(script_path)]
    )
    started = time.time()
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    log_path.write_text(output, encoding="utf-8")
    os.chmod(log_path, 0o600)
    receipt = {
        "schema": "frost.clipboard_autorun.receipt.v1",
        "captured_at": now_iso(),
        "sha256": digest,
        "shell": shell,
        "script_path": str(script_path),
        "log_path": str(log_path),
        "exit_code": completed.returncode,
        "duration_seconds": round(time.time() - started, 6),
        "autorun_marker_required": True,
    }
    write_json(receipt_path, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
