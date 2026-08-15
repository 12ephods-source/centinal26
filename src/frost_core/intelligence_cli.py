from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .intelligence_controller import IntelligenceController, canonical_json


def state_home() -> Path:
    return Path(os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26")).expanduser()


def controller() -> IntelligenceController:
    timezone_name = os.environ.get("CENTINAL26_TIMEZONE", "America/Mexico_City")
    return IntelligenceController(state_home() / "intelligence.sqlite3", timezone_name=timezone_name)


def _json_object(text: str, *, name: str) -> dict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise SystemExit(f"{name} must be valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"{name} must decode to a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(prog="centinal26-intelligence")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("cycle")

    daemon = sub.add_parser("daemon")
    daemon.add_argument("--poll", type=float, default=10.0)

    register = sub.add_parser("register")
    register.add_argument("conversation_key")
    register.add_argument("title")
    register.add_argument("--project", default="Automation")
    register.add_argument("--review-class", default="P2")
    register.add_argument("--strategic-value", type=float, default=0.5)
    register.add_argument("--status", default="ACTIVE")
    register.add_argument("--unresolved-count", type=int, default=0)
    register.add_argument("--notes", default="")

    import_registry = sub.add_parser("import-registry")
    import_registry.add_argument("path", type=Path)

    sub.add_parser("next-review")

    observe = sub.add_parser("observe")
    observe.add_argument("source_kind")
    observe.add_argument("source_key")
    observe.add_argument("change_type")
    observe.add_argument("severity")
    observe.add_argument("--evidence", required=True)
    observe.add_argument("--contradiction", default="{}")
    observe.add_argument("--non-material", action="store_true")

    review = sub.add_parser("review")
    review.add_argument("conversation_key")
    review.add_argument("--review-json", required=True)

    sub.add_parser("due")

    claim = sub.add_parser("claim")
    claim.add_argument("work_key")
    claim.add_argument("--claimer", required=True)
    claim.add_argument("--lease-seconds", type=int, default=300)

    complete = sub.add_parser("complete")
    complete.add_argument("work_key")
    complete.add_argument("--result", required=True)

    args = parser.parse_args()
    ctl = controller()
    try:
        if args.command in {"init", "status"}:
            print(canonical_json(ctl.status()))
        elif args.command == "cycle":
            print(canonical_json(ctl.cycle()))
        elif args.command == "daemon":
            ctl.run_forever(poll_seconds=args.poll)
        elif args.command == "register":
            ctl.register_conversation(
                args.conversation_key,
                args.title,
                project=args.project,
                review_class=args.review_class,
                strategic_value=args.strategic_value,
                status=args.status,
                unresolved_count=args.unresolved_count,
                notes=args.notes,
            )
            print(canonical_json({"registered": args.conversation_key}))
        elif args.command == "import-registry":
            data = json.loads(args.path.expanduser().read_text(encoding="utf-8"))
            if isinstance(data, dict) and "entities" in data:
                data = data["entities"]
            if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
                raise SystemExit("registry must be a JSON array of objects")
            print(canonical_json({"imported": ctl.import_registry(data)}))
        elif args.command == "next-review":
            print(canonical_json({"conversation": ctl.next_conversation()}))
        elif args.command == "observe":
            result = ctl.observe(
                source_kind=args.source_kind,
                source_key=args.source_key,
                change_type=args.change_type,
                severity=args.severity,
                evidence=_json_object(args.evidence, name="--evidence"),
                contradiction=_json_object(args.contradiction, name="--contradiction"),
                material_change=not args.non_material,
            )
            print(canonical_json({"event": result}))
        elif args.command == "review":
            data = _json_object(args.review_json, name="--review-json")
            required = {
                "unique_signal",
                "contradiction",
                "open_loop",
                "decision",
                "implementation_state",
                "architectural_implication",
                "confidence",
                "source_basis",
            }
            missing = sorted(required - set(data))
            if missing:
                raise SystemExit(f"review JSON missing: {', '.join(missing)}")
            digest = ctl.record_review(args.conversation_key, **{key: data[key] for key in required})
            print(canonical_json({"conversation_key": args.conversation_key, "review_hash": digest}))
        elif args.command == "due":
            print(canonical_json({"work": ctl.due_work()}))
        elif args.command == "claim":
            print(
                canonical_json(
                    {
                        "work": ctl.claim_work(
                            args.work_key,
                            claimer=args.claimer,
                            lease_seconds=args.lease_seconds,
                        )
                    }
                )
            )
        elif args.command == "complete":
            ctl.complete_work(
                args.work_key,
                result=_json_object(args.result, name="--result"),
            )
            print(canonical_json({"completed": args.work_key}))
    finally:
        ctl.close()


if __name__ == "__main__":
    main()
