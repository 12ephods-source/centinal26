"""Android worker executor scaffold.

The worker must be enrolled, authorized, and verified before use.
"""

from datetime import UTC, datetime


class AndroidWorkerExecutor:
    executor_id = "android_worker_executor"

    def health_check(self):
        return {"executor": self.executor_id, "status": "PENDING_WORKER"}

    def can_execute(self, request):
        return request.get("executor_id") == self.executor_id

    def execute(self, request):
        return {
            "task_id": request.get("task_id"),
            "executor": self.executor_id,
            "status": "PENDING_DEVICE_VERIFICATION",
            "timestamp": datetime.now(UTC).isoformat(),
        }
