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
    # Let argparse derive the displayed program name from argv[0].
    # This keeps both the canonical `wazoo26` CLI and the legacy `centinal26`
    # compatibility entry point truthful without maintaining two parsers.
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

    if args.command == "init":
        home = state_home()
        home.mkdir(parents=True, exist_ok=True)
        store = JobStore(home / "queue.sqlite3")
        AuditLog(home / "audit.jsonl")
        EventStore(home / "events.sqlite3").close()
        print(json.dumps({"status": "initialized", "home": str(home), "jobs": len(store.all())}))
        return

    if args.command == "demo":
        runtime = engine()
        grant = short_grant("system.echo")
        job_id = runtime.submit("system.echo", {"message": "hello"}, grant)
        result = runtime.run_once()
        print(json.dumps({"job_id": job_id, "result": result}, indent=2, sort_keys=True))
        return

    if args.command == "run-once":
        result = engine().run_once()
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if args.command == "status":
        home = state_home()
        store = JobStore(home / "queue.sqlite3")
        rows = store.all()
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.state] = counts.get(row.state, 0) + 1
        print(json.dumps({"home": str(home), "jobs": len(rows), "states": counts}, indent=2, sort_keys=True))
        return

    if args.command == "qualify":
        print(json.dumps(run_qualification(args.output), indent=2, sort_keys=True))
        return

    if args.command == "verify-evidence":
        print(json.dumps(verify_bundle(args.bundle), indent=2, sort_keys=True))
        return

    if args.command == "assess-evidence":
        result = assess_bundle(args.bundle)
        if args.output:
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if args.command == "state-init":
        store = event_store()
        print(json.dumps(state_summary(store), indent=2, sort_keys=True))
        store.close()
        return

    if args.command == "event-append":
        payload = json.loads(args.payload)
        store = event_store()
        event = store.append(args.type, payload, entity_id=args.entity_id)
        print(json.dumps(event.as_dict(), indent=2, sort_keys=True))
        store.close()
        return

    if args.command == "state-rebuild":
        store = event_store()
        state = rebuild_state(store.events())
        print(json.dumps(state.as_dict(), indent=2, sort_keys=True))
        store.close()
        return

    if args.command == "state-status":
        store = event_store()
        print(json.dumps(state_summary(store), indent=2, sort_keys=True))
        store.close()
        return

    if args.command == "ingest":
        store = event_store()
        discovered = discover_paths(args.paths, recursive=args.recursive)
        records = [ingest_path(store, path, max_bytes=args.max_bytes) for path in discovered]
        print(json.dumps(records, indent=2, sort_keys=True))
        store.close()
        return

    if args.command == "advance":
        store = event_store()
        runtime = build_advance_engine(state_home(), store)
        result = advance_until_idle(
            store,
            runtime,
            authorize=args.authorize,
            max_tasks=args.max_tasks if args.until_idle else 1,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        store.close()
        return

    if args.command == "auto-demo":
        runtime = automated_engine()
        job = runtime.submit(Intent("system.echo", {"message": "hello"}), short_grant("system.echo"))
        result = runtime.run_once()
        print(json.dumps({"job_id": job, "result": result}, indent=2, sort_keys=True))
        return

    if args.command == "auto-run-once":
        result = automated_engine().run_once()
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if args.command == "auto-daemon":
        automated_engine().run_daemon(poll_seconds=args.poll)
        return

    if args.command == "auto-selftest":
        runtime = automated_engine()
        print(json.dumps(runtime.selftest(), indent=2, sort_keys=True))
        return

    if args.command == "auto-status":
        print(json.dumps(automated_engine().status(), indent=2, sort_keys=True))
        return


if __name__ == "__main__":
    main()
