from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .core import AuditLog, Engine, Grant, JobStore
from .qualification import run_qualification, verify_bundle


def state_home() -> Path:
    return Path(os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26")).expanduser()


def echo(data: dict) -> dict:
    return {"echo": data}


def engine() -> Engine:
    home = state_home()
    runtime = Engine(JobStore(home / "queue.sqlite3"), AuditLog(home / "audit.jsonl"))
    runtime.register("system.echo", echo)
    return runtime


def main() -> None:
    parser = argparse.ArgumentParser(prog="centinal26")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("demo")
    sub.add_parser("run-once")
    sub.add_parser("status")
    qualify = sub.add_parser("qualify")
    qualify.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-evidence")
    verify.add_argument("bundle", type=Path)
    args = parser.parse_args()

    if args.command == "qualify":
        report = run_qualification(args.output.expanduser())
        print(json.dumps(report, sort_keys=True))
        raise SystemExit(0 if report["passed"] else 1)
    if args.command == "verify-evidence":
        valid = verify_bundle(args.bundle.expanduser())
        print(json.dumps({"bundle": str(args.bundle), "valid": valid}, sort_keys=True))
        raise SystemExit(0 if valid else 1)

    runtime = engine()
    if args.command == "init":
        print(json.dumps({"initialized": str(state_home())}))
    elif args.command == "demo":
        grant = Grant(
            grant_id=str(uuid.uuid4()),
            capability="system.echo",
            expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        )
        job_id = runtime.submit("system.echo", {"message": "Centinal26 online"}, grant)
        runtime.run_once()
        print(json.dumps({"job_id": job_id, "state": "verified"}))
    elif args.command == "run-once":
        print(json.dumps({"job_id": runtime.run_once()}))
    elif args.command == "status":
        print(json.dumps({
            "jobs": runtime.store.counts(),
            "audit_valid": runtime.audit.verify(),
            "home": str(state_home()),
        }, sort_keys=True))


if __name__ == "__main__":
    main()
