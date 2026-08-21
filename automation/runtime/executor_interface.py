"""
Automation OS Runtime Executor Interface

Separates task scheduling from task execution.

Scheduler responsibilities:
- create and prioritize tasks
- select candidate capabilities
- submit execution requests

Executor responsibilities:
- receive authorized execution requests
- invoke a verified capability adapter
- return structured results
- preserve execution metadata

Invariant:
queued != executed != verified
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from centinal26.governance import validate_bundle


@dataclass
class ExecutionRequest:
    task_id: str
    capability_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    authorization_status: str = "PENDING"
    governance_bundle: dict[str, Any] | None = None
    governance_required: bool = False


@dataclass
class ExecutionResult:
    task_id: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class Executor(Protocol):
    """Interface implemented by verified execution backends."""

    def can_execute(self, request: ExecutionRequest) -> bool:
        ...

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...


class ExecutorRegistry:
    """Maps verified capabilities to execution backends."""

    def __init__(self):
        self.executors: dict[str, Executor] = {}

    def register(self, capability_id: str, executor: Executor) -> None:
        self.executors[capability_id] = executor

    def get(self, capability_id: str):
        return self.executors.get(capability_id)

    def _governance_gate(self, request: ExecutionRequest) -> ExecutionResult | None:
        bundle = request.governance_bundle
        if bundle is None:
            if not request.governance_required:
                return None
            return ExecutionResult(
                task_id=request.task_id,
                status="GOVERNANCE_REQUIRED",
                output={"reason": "governance bundle required before execution"},
            )

        violations = validate_bundle(bundle)
        if violations:
            return ExecutionResult(
                task_id=request.task_id,
                status="GOVERNANCE_REJECTED",
                output={"violations": [item.as_dict() for item in violations]},
            )

        operations = bundle.get("operations", [])
        matching = [
            operation
            for operation in operations
            if operation.get("operation_id") == request.task_id
            and operation.get("capability_id") == request.capability_id
        ]
        if len(matching) != 1:
            return ExecutionResult(
                task_id=request.task_id,
                status="GOVERNANCE_REQUEST_MISMATCH",
                output={
                    "reason": "exactly one governed operation must match task and capability"
                },
            )
        return None

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        governance_result = self._governance_gate(request)
        if governance_result is not None:
            return governance_result

        executor = self.get(request.capability_id)
        if executor is None:
            return ExecutionResult(
                task_id=request.task_id,
                status="NO_EXECUTOR_AVAILABLE"
            )

        if not executor.can_execute(request):
            return ExecutionResult(
                task_id=request.task_id,
                status="EXECUTOR_REJECTED"
            )

        return executor.execute(request)
