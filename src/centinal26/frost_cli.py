from __future__ import annotations

import argparse
import json
import re
from typing import Any

from .advance import advance_until_idle, build_advance_engine
from .cli import event_store, state_home
from .event_state import state_summary


_OPERATOR_ALIASES = {
    "proceed": "PROCEED",
    "continue": "PROCEED",
    "implement": "PROCEED",
    "next": "PROCEED",
    "run": "PROCEED",
    "run it": "PROCEED",
    "do it": "PROCEED",
    "state": "STATE",
    "status": "STATE",
    "project state": "STATE",
    "where are we": "STATE",
    "verify": "VERIFY",
    "check": "VERIFY",
    "is that true": "VERIFY",
    "autopilot": "AUTOPILOT",
    "automatic": "AUTOPILOT",
    "proceed automatically": "AUTOPILOT",
    "run automatically": "AUTOPILOT",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def classify_operator(value: str) -> str:
    normalized = _normalize_text(value)
    try:
        return _OPERATOR_ALIASES[normalized]
    except KeyError as error:
        raise ValueError(f"unsupported frost intent: {value!r}") from error


def _advance_payload(report) -> dict[str, Any]:
    return report.as_dict()


def run_operator(
    operator: str,
    *,
    authorize: bool = False,
    max_tasks: int = 100,
) -> dict[str, Any]:
    if max_tasks < 1:
        raise ValueError("max_tasks must be positive")
    if max_tasks > 1000:
        raise ValueError("max_tasks may not exceed 1000")

    store = event_store()
    try:
        if operator == "STATE":
            return {
                "operator": operator,
                "state": state_summary(store),
            }

        if operator == "VERIFY":
            runtime = build_advance_engine(state_home())
            return {
                "operator": operator,
                "event_chain_valid": store.verify_chain(),
                "runtime_audit_valid": runtime.audit.verify(),
                "state": state_summary(store),
            }

        runtime = build_advance_engine(state_home())
        if operator == "PROCEED":
            report = advance_until_idle(
                store,
                runtime,
                authorize=True,
                max_tasks=1,
            )
            return {
                "operator": operator,
                "authorization_source": "explicit_frost_proceed_invocation",
                "advance": _advance_payload(report),
                "state": state_summary(store),
            }

        if operator == "AUTOPILOT":
            report = advance_until_idle(
                store,
                runtime,
                authorize=authorize,
                max_tasks=max_tasks,
            )
            return {
                "operator": operator,
                "authorization_source": (
                    "explicit_frost_autopilot_authorization" if authorize else None
                ),
                "advance": _advance_payload(report),
                "state": state_summary(store),
            }

        raise ValueError(f"unsupported frost operator: {operator}")
    finally:
        store.close()


def _exit_code(result: dict[str, Any]) -> int:
    operator = result["operator"]
    if operator == "VERIFY":
        return 0 if result["event_chain_valid"] and result["runtime_audit_valid"] else 2
    if operator in {"PROCEED", "AUTOPILOT"}:
        stop_reason = result["advance"]["stop_reason"]
        if stop_reason in {"COMPLETE", "IDLE", "RESOURCE_LIMIT"}:
            return 0
        if stop_reason == "APPROVAL_REQUIRED":
            return 3
        return 4
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="frost",
        description=(
            "Terse operator interface over Centinal26 canonical state, advance, "
            "authorization, execution and verification machinery."
        ),
    )
    parser.add_argument("intent", nargs="+")
    parser.add_argument(
        "--authorize",
        action="store_true",
        help="Explicitly authorize the bounded multi-task autopilot run.",
    )
    parser.add_argument("--max-tasks", type=int, default=100)
    parser.add_argument("--classify-only", action="store_true")
    args = parser.parse_args()

    phrase = " ".join(args.intent)
    try:
        operator = classify_operator(phrase)
        if args.classify_only:
            result = {"intent": phrase, "operator": operator}
            print(json.dumps(result, sort_keys=True))
            return
        result = run_operator(
            operator,
            authorize=args.authorize,
            max_tasks=args.max_tasks,
        )
    except ValueError as error:
        parser.error(str(error))

    print(json.dumps(result, sort_keys=True))
    raise SystemExit(_exit_code(result))


if __name__ == "__main__":
    main()
