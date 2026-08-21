"""Autonomy-first agent execution policy and task router.

This module models broad repository-operational capability while preserving a
small recovery trust root. It does not contain credentials or bypass provider
permissions; adapters must enforce the returned decision at execution time.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "agent_authority.json"


@dataclass(frozen=True)
class Decision:
    status: str
    role: str
    action: str
    requires_judge: bool
    reason: str


def load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def authorize(role: str, action: str, consequential: bool = False) -> Decision:
    policy = load_policy()
    roles = policy["roles"]
    if role not in roles:
        return Decision("DENY", role, action, False, "unknown role")
    if action in set(policy["root_deny"]):
        return Decision("ROOT_DENY", role, action, False, "protected recovery-root operation")
    role_policy = roles[role]
    if not role_policy.get("mutating", False) and action.startswith("write:"):
        return Decision("DENY_ROLE_MODE", role, action, False, "role is non-mutating by default")
    return Decision(
        "AUTHORIZED_BOUNDED",
        role,
        action,
        consequential,
        "broad repository authority subject to external adapter permissions and controls",
    )


def select_role(task_class: str) -> str:
    mapping = {
        "plan": "planner",
        "build": "builder",
        "verify": "judge",
        "repair": "sre",
        "audit": "sentinel",
        "release": "release",
    }
    return mapping.get(task_class, "planner")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_class", choices=["plan", "build", "verify", "repair", "audit", "release"])
    parser.add_argument("action")
    parser.add_argument("--consequential", action="store_true")
    args = parser.parse_args()
    role = select_role(args.task_class)
    decision = authorize(role, args.action, args.consequential)
    print(json.dumps(decision.__dict__, indent=2, sort_keys=True))
    if decision.status not in {"AUTHORIZED_BOUNDED"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
