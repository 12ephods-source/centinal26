from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .fleet_controller import FleetController, canonical_json


def state_home() -> Path:
    return Path(os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26")).expanduser()


def controller() -> FleetController:
    return FleetController(state_home() / "intelligence.sqlite3")


def _json(text: str, name: str) -> dict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise SystemExit(f"{name} must be valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"{name} must decode to an object")
    return value


def _list(value: object, name: str) -> list:
    if not isinstance(value, list):
        raise SystemExit(f"{name} must be a JSON array")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(prog="centinal26-fleet")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("metrics")

    contract = sub.add_parser("contract")
    contract.add_argument("--json", required=True)

    claim = sub.add_parser("claim")
    claim.add_argument("role")
    claim.add_argument("--claimer", required=True)
    claim.add_argument("--lease-seconds", type=int, default=600)
    claim.add_argument("--batch-limit", type=int, default=1)

    result = sub.add_parser("result")
    result.add_argument("contract_id")
    result.add_argument("role")
    result.add_argument("status")
    result.add_argument("--payload", required=True)
    result.add_argument("--evidence-hash", default="")

    pending = sub.add_parser("pending-verification")
    pending.add_argument("--limit", type=int, default=3)

    verdict = sub.add_parser("verdict")
    verdict.add_argument("result_id")
    verdict.add_argument("verdict")
    verdict.add_argument("--verifier", required=True)
    verdict.add_argument("--details", required=True)
    verdict.add_argument("--evidence-hash", default="")

    error = sub.add_parser("error")
    error.add_argument("subsystem")
    error.add_argument("event_type")
    error.add_argument("severity")
    error.add_argument("--recovered", action="store_true")
    error.add_argument("--details", default="{}")

    budget = sub.add_parser("error-budget")
    budget.add_argument("subsystem")

    args = parser.parse_args()
    ctl = controller()
    try:
        if args.command in {"init", "status"}:
            print(canonical_json(ctl.status()))
        elif args.command == "metrics":
            print(canonical_json(ctl.metrics(persist=True)))
        elif args.command == "contract":
            data = _json(args.json, "--json")
            for field in ("source_basis", "rollback_plan", "resource_budget", "ranking"):
                if field in data and not isinstance(data[field], dict):
                    raise SystemExit(f"{field} must be an object")
            for field in (
                "success_criteria", "allowed_scope", "prohibited_scope", "dependencies",
                "verification_requirements", "failure_criteria",
            ):
                if field in data:
                    data[field] = _list(data[field], field)
            print(canonical_json(ctl.create_contract(**data)))
        elif args.command == "claim":
            print(canonical_json({"contracts": ctl.claim_next(
                args.role, claimer=args.claimer, lease_seconds=args.lease_seconds,
                batch_limit=args.batch_limit,
            )}))
        elif args.command == "result":
            print(canonical_json(ctl.record_result(
                args.contract_id, role=args.role, status=args.status,
                payload=_json(args.payload, "--payload"), evidence_hash=args.evidence_hash,
            )))
        elif args.command == "pending-verification":
            print(canonical_json({"results": ctl.pending_verification(limit=args.limit)}))
        elif args.command == "verdict":
            print(canonical_json(ctl.record_verdict(
                args.result_id, verdict=args.verdict, verifier=args.verifier,
                details=_json(args.details, "--details"), evidence_hash=args.evidence_hash,
            )))
        elif args.command == "error":
            print(canonical_json(ctl.record_error_event(
                subsystem=args.subsystem, event_type=args.event_type, severity=args.severity,
                recovered=args.recovered, details=_json(args.details, "--details"),
            )))
        elif args.command == "error-budget":
            print(canonical_json(ctl.error_budget(args.subsystem)))
    finally:
        ctl.close()


if __name__ == "__main__":
    main()
