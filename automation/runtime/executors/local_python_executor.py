"""Local Python executor scaffold.

Executes only explicitly assigned bounded tasks. Scheduling, authorization, and
verification remain outside this executor.
"""

from datetime import UTC, datetime


class LocalPythonExecutor:
    executor_id = "local_python_executor"
    capabilities = ("local_python",)

    def health_check(self):
        return {
            "executor_id": self.executor_id,
            "status": "READY",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def can_execute(self, request):
        return (
            request.get("capability_id") in self.capabilities
            and request.get("authorization_status") == "AUTHORIZED"
        )

    def execute(self, request):
        if not self.can_execute(request):
            return {
                "task_id": request.get("task_id"),
                "executor_id": self.executor_id,
                "status": "REJECTED",
                "timestamp": datetime.now(UTC).isoformat(),
                "reason": "capability_or_authorization",
            }
        return {
            "task_id": request.get("task_id"),
            "executor_id": self.executor_id,
            "status": "COMPLETED",
            "timestamp": datetime.now(UTC).isoformat(),
            "note": "Execution scaffold; production sandboxing required.",
        }
