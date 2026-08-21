"""Integration harness for the controlled Automation OS execution path.

This harness exercises real repository components rather than a private mock:
registry -> authorization/capability gate -> executor -> evidence -> validator,
and the canonical Centinal26 bounded agent execution plane.

A PASS here is integration evidence, not production or physical-device proof.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from centinal26.agent_execution_plane import run_task

from automation.execution.result_validator import validate
from automation.runtime.evidence.evidence_generator import create_evidence, hash_record
from automation.runtime.executors.android_worker_executor import AndroidWorkerExecutor
from automation.runtime.executors.api_connector_executor import APIConnectorExecutor
from automation.runtime.executors.local_python_executor import LocalPythonExecutor
from automation.runtime.executors.repository_executor import RepositoryExecutor

REGISTRY_PATH = ROOT / "automation" / "runtime" / "executor_registry.json"


def _request(task_id: str, capability_id: str, authorized: bool = True) -> dict:
    return {
        "task_id": task_id,
        "capability_id": capability_id,
        "authorization_status": "AUTHORIZED" if authorized else "PENDING",
        "payload": {"operation": "integration_validation"},
    }


def _assert_executor_contract(executor, capability_id: str) -> dict:
    health = executor.health_check()
    assert health["executor_id"] == executor.executor_id
    assert "status" in health and "timestamp" in health

    unauthorized = _request(f"{executor.executor_id}-deny", capability_id, False)
    assert not executor.can_execute(unauthorized)
    rejected = executor.execute(unauthorized)
    assert rejected["status"] == "REJECTED"

    authorized = _request(f"{executor.executor_id}-allow", capability_id, True)
    assert executor.can_execute(authorized)
    result = executor.execute(authorized)
    assert result["task_id"] == authorized["task_id"]
    assert result["executor_id"] == executor.executor_id
    assert "status" in result and "timestamp" in result
    assert validate(result)

    evidence = create_evidence(
        request=authorized,
        result=result,
        verification={"status": "INTEGRATION_CHECKED"},
    )
    digest = hash_record(evidence)
    assert len(digest) == 64
    assert digest == hash_record(evidence)
    return {"health": health["status"], "result": result["status"], "digest": digest}


def run_integration_test() -> dict:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    ids = [item["executor_id"] for item in registry["executors"]]
    assert len(ids) == len(set(ids))
    assert registry["request_contract"]["authorized_value"] == "AUTHORIZED"
    assert registry["selection_policy"]["require_independent_validation"] is True

    executor_results = {
        "local_python_executor": _assert_executor_contract(
            LocalPythonExecutor(), "local_python"
        ),
        "repository_executor": _assert_executor_contract(
            RepositoryExecutor(), "repository_operation"
        ),
        "api_connector_executor": _assert_executor_contract(
            APIConnectorExecutor(), "api_connector"
        ),
    }

    android = AndroidWorkerExecutor()
    assert android.health_check()["status"] == "PENDING_WORKER"
    assert android.can_execute(_request("android-pending", "android_worker", True))
    assert android.execute(_request("android-pending", "android_worker", True))["status"] == (
        "PENDING_DEVICE_VERIFICATION"
    )

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bounded = run_task(
            {
                "role": "builder",
                "command": [sys.executable, "-c", "print('executor-plane-ok')"],
                "capabilities": [],
                "timeout": 30,
            },
            root,
        )
        assert bounded["status"] == "PASS"
        assert "executor-plane-ok" in bounded["stdout"]
        assert len(bounded["task_digest"]) == 64
        assert len(bounded["evidence_digest"]) == 64

        blocked = run_task(
            {
                "role": "sre",
                "command": [sys.executable, "-c", "raise SystemExit(99)"],
                "capabilities": ["credential_root"],
            },
            root,
        )
        assert blocked["status"] == "BLOCKED_ROOT_DENY"
        assert "credential_root" in blocked["denied"]

    return {
        "status": "PASS",
        "stage": "executor_integration",
        "registry_status": registry["status"],
        "executors": executor_results,
        "canonical_agent_plane": "PASS",
        "root_deny_gate": "PASS",
        "android_physical_gate": "PENDING_PHYSICAL_WORKER",
    }


if __name__ == "__main__":
    print(json.dumps(run_integration_test(), indent=2, sort_keys=True))
