from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from .advance import advance_until_idle, build_advance_engine
from .event_state import EventStore, derive_ready_tasks, rebuild_state, state_summary

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
    "criticize": "CRITIQUE",
    "critique": "CRITIQUE",
    "criticism": "CRITIQUE",
    "adversarial": "CRITIQUE",
    "opposite opinion": "CRITIQUE",
    "fix": "REPAIR",
    "fix this": "REPAIR",
    "fix everything": "REPAIR",
    "repair": "REPAIR",
    "automate": "AUTOMATE",
    "automate this": "AUTOMATE",
    "autopilot": "AUTOPILOT",
    "automatic": "AUTOPILOT",
    "proceed automatically": "AUTOPILOT",
    "run automatically": "AUTOPILOT",
}


def state_home() -> Path:
    return Path(os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26")).expanduser()


def event_store() -> EventStore:
    return EventStore(state_home() / "events.sqlite3")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def classify_operator(value: str) -> str:
    normalized = _normalize_text(value)
    try:
        return _OPERATOR_ALIASES[normalized]
    except KeyError as error:
        raise ValueError(f"unsupported frost intent: {value!r}") from error


def _advance_payload(report) -> dict[str, object]:
    return report.as_dict()


def _critique(store: EventStore) -> dict[str, object]:
    chain_valid = store.verify_chain()
    if not chain_valid:
        return {
            "event_chain_valid": False,
            "issues": [
                {
                    "severity": "CRITICAL",
                    "kind": "EVENT_CHAIN_INVALID",
                    "detail": "canonical event history failed hash-chain verification",
                }
            ],
            "ready_tasks": [],
            "promotion_authority": False,
            "execution_authority": False,
        }

    state = rebuild_state(store.events())
    issues: list[dict[str, object]] = []
    for blocker_id, blocker in sorted(state.blockers.items()):
        issues.append(
            {
                "severity": "HIGH",
                "kind": "BLOCKER",
                "blocker_id": blocker_id,
                "task_id": blocker.get("task_id"),
                "reason": blocker.get("reason"),
                "detail": blocker.get("detail"),
            }
        )

    for task_id, task in sorted(state.tasks.items()):
        status = task.get("status")
        if status in {"FAILED", "VERIFICATION_FAILED"}:
            issues.append(
                {
                    "severity": "HIGH",
                    "kind": "TASK_FAILURE",
                    "task_id": task_id,
                    "status": status,
                    "capability": task.get("capability"),
                }
            )

    return {
        "event_chain_valid": True,
        "issues": issues,
        "ready_tasks": derive_ready_tasks(state),
        "promotion_authority": False,
        "execution_authority": False,
    }


def _automation_candidates(store: EventStore) -> dict[str, object]:
    chain_valid = store.verify_chain()
    if not chain_valid:
        return {
            "event_chain_valid": False,
            "candidates": [],
            "reason": "EVENT_CHAIN_INVALID",
            "promotion_authority": False,
            "execution_authority": False,
        }

    state = rebuild_state(store.events())
    grouped: dict[str, list[str]] = {}
    for task_id, task in sorted(state.tasks.items()):
        if task.get("status") in {"COMPLETE", "FAILED", "VERIFICATION_FAILED"}:
            continue
        capability = task.get("capability")
        objective = task.get("objective")
        if isinstance(capability, str) and capability.strip():
            signature = f"capability:{capability.strip()}"
        elif isinstance(objective, str) and objective.strip():
            signature = f"objective:{_normalize_text(objective)}"
        else:
            signature = "unclassified"
        grouped.setdefault(signature, []).append(task_id)

    blocked_tasks: dict[str, list[str]] = {}
    for blocker in state.blockers.values():
        task_id = blocker.get("task_id")
        reason = blocker.get("reason")
        if not isinstance(task_id, str) or not isinstance(reason, str):
            continue
        if reason in {"NO_CAPABILITY", "VERIFIER_NOT_INDEPENDENT"}:
            blocked_tasks.setdefault(task_id, []).append(reason)

    candidates: list[dict[str, object]] = []
    for signature, task_ids in sorted(grouped.items()):
        reasons: list[str] = []
        if len(task_ids) >= 2:
            reasons.append("REPEATED_PATTERN")
        blocked_reasons = sorted(
            {reason for task_id in task_ids for reason in blocked_tasks.get(task_id, [])}
        )
        reasons.extend(blocked_reasons)
        if not reasons:
            continue
        candidates.append(
            {
                "candidate_id": f"automation:{signature}",
                "signature": signature,
                "task_ids": task_ids,
                "occurrences": len(task_ids),
                "reasons": reasons,
                "status": "CANDIDATE_ONLY",
            }
        )

    return {
        "event_chain_valid": True,
        "candidates": candidates,
        "promotion_authority": False,
        "execution_authority": False,
        "note": "candidate discovery does not register, enable, or promote executable code",
    }


def run_operator(
    operator: str,
    *,
    authorize: bool = False,
    max_tasks: int = 100,
) -> dict[str, object]:
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

        if operator == "CRITIQUE":
            return {
                "operator": operator,
                "critique": _critique(store),
                "state": state_summary(store),
            }

        if operator == "AUTOMATE":
            return {
                "operator": operator,
                "automation": _automation_candidates(store),
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

        if operator == "REPAIR":
            report = advance_until_idle(
                store,
                runtime,
                authorize=False,
                max_tasks=max_tasks,
            )
            return {
                "operator": operator,
                "authorization_source": "safe_capability_policy_only",
                "advance": _advance_payload(report),
                "critique": _critique(store),
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


def _exit_code(result: dict[str, object]) -> int:
    operator = result["operator"]
    if operator == "VERIFY":
        return 0 if result["event_chain_valid"] and result["runtime_audit_valid"] else 2
    if operator == "CRITIQUE":
        critique = result["critique"]
        return 0 if isinstance(critique, dict) and critique["event_chain_valid"] else 2
    if operator == "AUTOMATE":
        automation = result["automation"]
        return 0 if isinstance(automation, dict) and automation["event_chain_valid"] else 2
    if operator in {"PROCEED", "REPAIR", "AUTOPILOT"}:
        advance = result["advance"]
        if not isinstance(advance, dict):
            return 4
        stop_reason = advance["stop_reason"]
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
