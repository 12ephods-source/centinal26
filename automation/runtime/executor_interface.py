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
from datetime import datetime, timezone
from typing import Any, Dict, Protocol


@dataclass
class ExecutionRequest:
    task_id: str
    capability_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    authorization_status: str = "PENDING"


@dataclass
class ExecutionResult:
    task_id: str
    status: str
    output: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
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
        self.executors: Dict[str, Executor] = {}

    def register(self, capability_id: str, executor: Executor) -> None:
        self.executors[capability_id] = executor

    def get(self, capability_id: str):
        return self.executors.get(capability_id)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
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
