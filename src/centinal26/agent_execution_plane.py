"""Minimal operational execution plane for qualified Frost agents."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

ROLES = ("planner", "builder", "judge", "sre", "sentinel")
ROOT_DENY = {"account_owner", "credential_root", "audit_destroy", "backup_destroy"}


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def run_task(task, root: Path):
    role = task.get("role", "builder")
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    requested = set(task.get("capabilities", []))
    denied = sorted(requested & ROOT_DENY)
    if denied:
        return {"status": "BLOCKED_ROOT_DENY", "denied": denied, "task": task}
    command = task.get("command")
    if not isinstance(command, list) or not command:
        return {"status": "INVALID_TASK", "task": task}
    timeout = min(int(task.get("timeout", 120)), 900)
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    result = {
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "role": role,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-12000:],
        "elapsed_s": round(time.time() - started, 3),
        "task_digest": digest(task),
    }
    result["evidence_digest"] = digest(result)
    return result


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
