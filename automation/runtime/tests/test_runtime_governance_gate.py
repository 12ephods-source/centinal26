from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from automation.runtime.executor_interface import ExecutionRequest, ExecutionResult, ExecutorRegistry


@dataclass
class _Executor:
    calls: int = 0

    def can_execute(self, request: ExecutionRequest) -> bool:
        return request.authorization_status == "AUTHORIZED"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(task_id=request.task_id, status="PASS")


def _bundle(task_id: str = "task-1", capability_id: str = "local_python") -> dict:
    now = datetime.now(UTC)
    scope = {"project": "automation"}
    return {
        "schema": "centinal26-governance-bundle-v1",
        "authorizations": [
            {
                "schema": "centinal26-authorization-v1",
                "authorization_id": "auth-1",
                "issuer": "operator",
                "subject": "runtime-worker",
                "capability": capability_id,
                "scope": scope,
                "risk_class": "LOW",
                "issued_at": (now - timedelta(minutes=1)).isoformat(),
                "expires_at": (now + timedelta(minutes=5)).isoformat(),
                "signature": "metadata-present-not-cryptographically-verified",
            }
        ],
        "evidence": [],
        "operations": [
            {
                "schema": "centinal26-operation-v1",
                "operation_id": task_id,
                "actor": "runtime-worker",
                "authorization_id": "auth-1",
                "capability_id": capability_id,
                "scope": scope,
                "risk_class": "LOW",
                "preconditions": [],
                "postconditions": ["structured execution result returned"],
                "destructive": False,
                "preservation_evidence_refs": [],
            }
        ],
        "claims": [],
        "promotions": [],
        "terminal_events": [],
    }


def _registry() -> tuple[ExecutorRegistry, _Executor]:
    executor = _Executor()
    registry = ExecutorRegistry()
    registry.register("local_python", executor)
    return registry, executor


def test_backward_compatible_request_without_required_governance_executes() -> None:
    registry, executor = _registry()
    result = registry.execute(
        ExecutionRequest(
            task_id="legacy-task",
            capability_id="local_python",
            authorization_status="AUTHORIZED",
        )
    )
    assert result.status == "PASS"
    assert executor.calls == 1


def test_required_governance_missing_fails_closed_before_executor() -> None:
    registry, executor = _registry()
    result = registry.execute(
        ExecutionRequest(
            task_id="task-1",
            capability_id="local_python",
            authorization_status="AUTHORIZED",
            governance_required=True,
        )
    )
    assert result.status == "GOVERNANCE_REQUIRED"
    assert executor.calls == 0


def test_invalid_governance_rejected_before_executor() -> None:
    registry, executor = _registry()
    bundle = _bundle()
    bundle["authorizations"][0]["issuer"] = "runtime-worker"
    result = registry.execute(
        ExecutionRequest(
            task_id="task-1",
            capability_id="local_python",
            authorization_status="AUTHORIZED",
            governance_bundle=bundle,
            governance_required=True,
        )
    )
    assert result.status == "GOVERNANCE_REJECTED"
    assert any(
        item["code"] == "SELF_AUTHORIZATION_FORBIDDEN"
        for item in result.output["violations"]
    )
    assert executor.calls == 0


def test_governance_task_capability_mismatch_rejected_before_executor() -> None:
    registry, executor = _registry()
    result = registry.execute(
        ExecutionRequest(
            task_id="different-task",
            capability_id="local_python",
            authorization_status="AUTHORIZED",
            governance_bundle=_bundle(),
            governance_required=True,
        )
    )
    assert result.status == "GOVERNANCE_REQUEST_MISMATCH"
    assert executor.calls == 0


def test_valid_governance_allows_executor() -> None:
    registry, executor = _registry()
    result = registry.execute(
        ExecutionRequest(
            task_id="task-1",
            capability_id="local_python",
            authorization_status="AUTHORIZED",
            governance_bundle=_bundle(),
            governance_required=True,
        )
    )
    assert result.status == "PASS"
    assert executor.calls == 1
