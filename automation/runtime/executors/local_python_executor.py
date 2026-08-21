"""Local Python executor scaffold.

Executes only explicitly assigned bounded tasks.
"""

from datetime import UTC, datetime


class LocalPythonExecutor:
    executor_id = "local_python_executor"

    def health_check(self):
        return {"executor": self.executor_id, "status": "READY"}

    def can_execute(self, request):
        return request.get("executor_id") == self.executor_id

    def execute(self, request):
        return {
            "task_id": request.get("task_id"),
            "executor": self.executor_id,
            "status": "COMPLETED",
            "timestamp": datetime.now(UTC).isoformat(),
            "note": "Execution scaffold; production sandboxing required.",
        }
