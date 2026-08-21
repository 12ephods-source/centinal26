"""Operational execution plane for qualified Frost agents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from frost_core.object_store import CanonicalObjectStore
from frost_core.runtime_governance import verify_runtime_objective_context

ROLES = ("planner", "builder", "judge", "sre", "sentinel", "release")
MAX_TIMEOUT_SECONDS = 900
POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "agent_authority.json"


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def load_authority_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _runtime_object_store(root: Path) -> CanonicalObjectStore:
    configured = os.environ.get("CENTINAL26_OBJECT_STORE", "").strip()
    path = Path(configured).expanduser() if configured else root / ".centinal26" / "objects.sqlite3"
    return CanonicalObjectStore(path)


def authorize_task(task: dict, *, root: Path | None = None) -> dict:
    """Return a bounded authority decision without executing the task."""
    try:
        policy = load_authority_policy()
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "POLICY_ERROR",
            "role": task.get("role", "builder"),
            "action": task.get("action"),
            "requires_judge": False,
            "reason": str(exc),
        }

    role = task.get("role", "builder")
    if role not in policy.get("roles", {}) or role not in ROLES:
        return {
            "status": "INVALID_ROLE",
            "role": role,
            "action": task.get("action"),
            "requires_judge": False,
            "reason": "unknown_role",
        }

    rules = policy.get("action_rules", {})
    action = task.get("action") or rules.get("default_action", "execute:bounded_task")
    if not isinstance(action, str) or not action:
        return {
            "status": "INVALID_TASK",
            "role": role,
            "action": action,
            "requires_judge": False,
            "reason": "invalid_action",
        }

    capabilities = task.get("capabilities", [])
    if not isinstance(capabilities, list) or not all(
        isinstance(item, str) and item for item in capabilities
    ):
        return {
            "status": "INVALID_TASK",
            "role": role,
            "action": action,
            "requires_judge": False,
            "reason": "invalid_capabilities",
        }

    root_deny = set(policy.get("root_deny", []))
    denied = sorted(set(capabilities) & root_deny)
    if action in root_deny:
        denied.append(action)
    if denied:
        return {
            "status": "BLOCKED_ROOT_DENY",
            "role": role,
            "action": action,
            "requires_judge": False,
            "denied": sorted(set(denied)),
            "reason": "protected_recovery_root_operation",
        }

    role_policy = policy["roles"][role]
    write_prefix = rules.get("write_prefix", "write:")
    is_mutation = action.startswith(write_prefix)
    if is_mutation and not role_policy.get("mutating", False):
        return {
            "status": "DENY_ROLE_MODE",
            "role": role,
            "action": action,
            "requires_judge": False,
            "reason": "role_non_mutating_by_default",
        }

    consequential = bool(task.get("consequential", False))
    requires_judge = bool(
        consequential
        and is_mutation
        and rules.get("consequential_requires_judge", True)
    )
    if requires_judge and task.get("judge_verified") is not True:
        return {
            "status": "REQUIRES_INDEPENDENT_JUDGE",
            "role": role,
            "action": action,
            "requires_judge": True,
            "reason": "consequential_mutation_not_independently_verified",
        }

    requires_objective = is_mutation or consequential
    if requires_objective:
        if not isinstance(task.get("objective_context"), dict):
            return {
                "status": "OBJECTIVE_CONTEXT_REQUIRED",
                "role": role,
                "action": action,
                "requires_judge": requires_judge,
                "reason": "consequential_or_mutating_task_missing_objective_context",
            }
        if root is None:
            return {
                "status": "OBJECTIVE_STORE_REQUIRED",
                "role": role,
                "action": action,
                "requires_judge": requires_judge,
                "reason": "runtime_object_store_not_available",
            }
        governance = verify_runtime_objective_context(
            _runtime_object_store(root),
            task,
            action_name=action,
        )
        if not governance.allowed:
            return {
                "status": governance.status,
                "role": role,
                "action": action,
                "requires_judge": requires_judge,
                "reason": governance.reason,
                "objective_id": governance.objective_id,
            }
    else:
        governance = None

    return {
        "status": "AUTHORIZED_BOUNDED",
        "role": role,
        "action": action,
        "requires_judge": requires_judge,
        "objective_id": None if governance is None else governance.objective_id,
        "reason": "policy_and_objective_authorized_subject_to_external_adapter_permissions",
    }


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
    authorization = authorize_task(task, root=root)
    if authorization["status"] != "AUTHORIZED_BOUNDED":
        return _result(
            authorization["status"],
            task,
            role=authorization.get("role"),
            action=authorization.get("action"),
            requires_judge=authorization.get("requires_judge", False),
            reason=authorization.get("reason"),
            denied=authorization.get("denied", []),
            objective_id=authorization.get("objective_id"),
        )

    role = authorization["role"]
    action = authorization["action"]
    command = task.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) and item for item in command)
    ):
        return _result("INVALID_TASK", task, role=role, action=action, reason="invalid_command")

    try:
        timeout = int(task.get("timeout", 120))
    except (TypeError, ValueError):
        return _result("INVALID_TASK", task, role=role, action=action, reason="invalid_timeout")
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
            action=action,
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
            action=action,
            returncode=None,
            stdout="",
            stderr=str(exc),
            elapsed_s=round(time.time() - started, 3),
        )

    return _result(
        "PASS" if proc.returncode == 0 else "FAIL",
        task,
        role=role,
        action=action,
        requires_judge=authorization["requires_judge"],
        objective_id=authorization.get("objective_id"),
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
