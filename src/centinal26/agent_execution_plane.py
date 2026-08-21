"""Operational execution plane for qualified Frost agents."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

ROLES = ("planner", "builder", "judge", "sre", "sentinel")
ROOT_DENY = {"account_owner", "credential_root", "audit_destroy", "backup_destroy"}
MAX_TIMEOUT_SECONDS = 900


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def _tail(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    return str(value)[-12000:]


def _result(status, task, **fields):
    result = {
        "status": status,
        "task_digest": digest(task),
        **fields,
    }
    result["evidence_digest"] = digest(result)
    return result


def run_task(task, root: Path):
    role = task.get("role", "builder")
    if role not in ROLES:
        return _result("INVALID_ROLE", task, role=role)

    requested = set(task.get("capabilities", []))
    denied = sorted(requested & ROOT_DENY)
    if denied:
        return _result("BLOCKED_ROOT_DENY", task, role=role, denied=denied)

    command = task.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) and item for item in command)
    ):
        return _result("INVALID_TASK", task, role=role, reason="invalid_command")

    try:
        timeout = int(task.get("timeout", 120))
    except (TypeError, ValueError):
        return _result("INVALID_TASK", task, role=role, reason="invalid_timeout")
    timeout = max(1, min(timeout, MAX_TIMEOUT_SECONDS))

    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _result(
            "TIMEOUT",
            task,
            role=role,
            returncode=None,
            stdout=_tail(exc.stdout),
            stderr=_tail(exc.stderr),
            elapsed_s=round(time.time() - started, 3),
            timeout_s=timeout,
        )
    except OSError as exc:
        return _result(
            "EXECUTION_ERROR",
            task,
            role=role,
            returncode=None,
            stdout="",
            stderr=str(exc),
            elapsed_s=round(time.time() - started, 3),
        )

    return _result(
        "PASS" if proc.returncode == 0 else "FAIL",
        task,
        role=role,
        returncode=proc.returncode,
        stdout=_tail(proc.stdout),
        stderr=_tail(proc.stderr),
        elapsed_s=round(time.time() - started, 3),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence", default="agent_evidence.json")
    args = parser.parse_args()
    task = json.loads(Path(args.task).read_text())
    result = run_task(task, Path(args.root))
    Path(args.evidence).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
