from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .advance import advance_until_idle, build_advance_engine
from .core import AuditLog, Engine, Grant, JobStore, Verification
from .event_state import EventStore, rebuild_state, state_summary
from .future import register_future_capabilities
from .ingest import DEFAULT_MAX_BYTES, discover_paths, ingest_path
from .pipeline import (
    AutomatedEngine,
    CapabilitySpec,
    EvidenceStore,
    Intent,
    RuntimeStore,
    echo_reducer,
    echo_verifier,
)
from .qualification import assess_bundle, run_qualification, verify_bundle


def state_home() -> Path:
    value = os.environ.get(
        "WAZOO26_HOME",
        os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26"),
    )
    return Path(value).expanduser()


def event_store() -> EventStore:
    return EventStore(state_home() / "events.sqlite3")


def echo(data: dict) -> dict:
    return {"echo": data}


def verify_echo(data: dict, output: dict) -> Verification:
    return Verification(
        passed=output == {"echo": data},
        evidence={"method": "exact_echo_match"},
    )


def engine() -> Engine:
    home = state_home()
    runtime = Engine(JobStore(home / "queue.sqlite3"), AuditLog(home / "audit.jsonl"))
    runtime.register("system.echo", echo, verify_echo)
    register_future_capabilities(runtime)
    return runtime


def automated_engine() -> AutomatedEngine:
    home = state_home()
    runtime = AutomatedEngine(
        RuntimeStore(home / "automation.sqlite3"),
        AuditLog(home / "automation-audit.jsonl"),
        EvidenceStore(home / "automation-evidence"),
    )
    runtime.register(
        CapabilitySpec(
            name="system.echo",
            executor=echo,
            verifier=echo_verifier,
            reducer=echo_reducer,
            verifier_independent=True,
        )
    )
    return runtime


def short_grant(capability: str) -> Grant:
    return Grant(
        grant_id=str(uuid.uuid4()),
        capability=capability,
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("demo")
    sub.add_parser("run-once")
    sub.add_parser("status")
    qualify = sub.add_parser("qualify")
    qualify.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-evidence")
    verify.add_argument("bundle", type=Path)
    assess = sub.add_parser("assess-evidence")
    assess.add_argument("bundle", type=Path)
    assess.add_argument("--output", type=Path)

    sub.add_parser("state-init")
    append_event = sub.add_parser("event-append")
    append_event.add_argument("type")
    append_event.add_argument("--entity-id")
    append_event.add_argument("--payload", default="{}")
    sub.add_parser("state-rebuild")
    sub.add_parser("state-status")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("paths", nargs="+", type=Path)
    ingest.add_argument("--recursive", action="store_true")
    ingest.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    advance = sub.add_parser("advance")
    advance.add_argument("--until-idle", action="store_true")
    advance.add_argument("--authorize", action="store_true")
    advance.add_argument("--max-tasks", type=int, default=100)

    sub.add_parser("auto-demo")
    sub.add_parser("auto-run-once")
    auto_daemon = sub.add_parser("auto-daemon")
    auto_daemon.add_argument("--poll", type=float, default=1.0)
    sub.add_parser("auto-selftest")
    sub.add_parser("auto-status")

    args = parser.parse_args()

    if args.command == "qualify":
        report = run_qualification(args.output.expanduser())
        print(json.dumps(report, sort_keys=True))
        raise SystemExit(0 if report["passed"] else 1)
    if args.command == "verify-evidence":
        valid = verify_bundle(args.bundle.expanduser())
        print(json.dumps({"bundle": str(args.bundle), "valid": valid}, sort_keys=True))
        raise SystemExit(0 if valid else 1)
    if args.command == "assess-evidence":
        report = assess_bundle(args.bundle.expanduser())
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.expanduser().write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        raise SystemExit(0 if report["decision"] != "INVALID" else 1)

    if args.command == "ingest":
        if args.max_bytes < 1:
            parser.error("--max-bytes must be positive")
        paths = discover_paths(args.paths, recursive=args.recursive)
        store = event_store()
        try:
            results = [
                ingest_path(store, path, max_bytes=args.max_bytes).as_dict() for path in paths
            ]
            print(
                json.dumps(
                    {"results": results, "state": state_summary(store)},
                    sort_keys=True,
                )
            )
        finally:
            store.close()
        return

    if args.command == "advance":
        if args.max_tasks < 1:
            parser.error("--max-tasks must be positive")
        store = event_store()
        try:
            runtime = build_advance_engine(state_home())
            budget = args.max_tasks if args.until_idle else 1
            report = advance_until_idle(
                store,
                runtime,
                authorize=args.authorize,
                max_tasks=budget,
            )
            print(
                json.dumps(
                    {"advance": report.as_dict(), "state": state_summary(store)},
                    sort_keys=True,
                )
            )
        finally:
            store.close()
        return

    if args.command.startswith("state-") or args.command == "event-append":
        store = event_store()
        try:
            if args.command == "state-init":
                print(
                    json.dumps(
                        {
                            "initialized": str(store.path),
                            "event_chain_valid": store.verify_chain(),
                        },
                        sort_keys=True,
                    )
                )
            elif args.command == "event-append":
                try:
                    payload = json.loads(args.payload)
                except json.JSONDecodeError as error:
                    parser.error(f"--payload must be valid JSON: {error}")
                if not isinstance(payload, dict):
                    parser.error("--payload must decode to a JSON object")
                event = store.append(args.type, payload, entity_id=args.entity_id)
                print(json.dumps(event.as_dict(), sort_keys=True))
            elif args.command == "state-rebuild":
                if not store.verify_chain():
                    print(json.dumps({"event_chain_valid": False}, sort_keys=True))
                    raise SystemExit(2)
                print(json.dumps(rebuild_state(store.events()).as_dict(), sort_keys=True))
            elif args.command == "state-status":
                summary = state_summary(store)
                print(json.dumps(summary, sort_keys=True))
                raise SystemExit(0 if summary["event_chain_valid"] else 2)
        finally:
            store.close()
        return

    if args.command.startswith("auto-"):
        runtime = automated_engine()
        if args.command == "auto-demo":
            intent = Intent(
                "system.echo",
                {"message": "Wazoo26 automated vertical slice online"},
            )
            job_id = runtime.submit(intent, short_grant(intent.capability))
            runtime.run_once()
            row = runtime.store.db.execute(
                "SELECT state,evidence_path FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            print(
                json.dumps(
                    {
                        "job_id": job_id,
                        "state": row["state"],
                        "evidence_path": row["evidence_path"],
                    },
                    sort_keys=True,
                )
            )
        elif args.command == "auto-run-once":
            print(json.dumps({"job_id": runtime.run_once()}))
        elif args.command == "auto-daemon":
            runtime.run_forever(poll_seconds=args.poll)
        elif args.command == "auto-selftest":
            intent = Intent("system.echo", {"selftest": "lease-recovery"})
            job_id = runtime.submit(intent, short_grant(intent.capability))
            claimed = runtime.store.claim(lease_seconds=60)
            if claimed is None or claimed["id"] != job_id:
                raise RuntimeError("selftest could not claim queued job")
            runtime.store.db.execute(
                "UPDATE jobs SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?",
                (job_id,),
            )
            runtime.store.db.commit()
            recovered = runtime.store.recover()
            runtime.run_once(recovery_test=True)
            print(
                json.dumps(
                    {
                        "job_id": job_id,
                        "recovered_leases": recovered,
                        "evolution": runtime.store.evolution_status(),
                    },
                    sort_keys=True,
                )
            )
        elif args.command == "auto-status":
            print(
                json.dumps(
                    {
                        "jobs": runtime.store.counts(),
                        "audit_valid": runtime.audit.verify(),
                        "evolution": runtime.store.evolution_status(),
                        "home": str(state_home()),
                    },
                    sort_keys=True,
                )
            )
        return

    runtime = engine()
    if args.command == "init":
        print(json.dumps({"initialized": str(state_home())}))
    elif args.command == "demo":
        grant = short_grant("system.echo")
        job_id = runtime.submit("system.echo", {"message": "Wazoo26 online"}, grant)
        runtime.run_once()
        print(json.dumps({"job_id": job_id, "state": "verified"}))
    elif args.command == "run-once":
        print(json.dumps({"job_id": runtime.run_once()}))
    elif args.command == "status":
        print(
            json.dumps(
                {
                    "jobs": runtime.store.counts(),
                    "audit_valid": runtime.audit.verify(),
                    "home": str(state_home()),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
