"""Android worker executor scaffold.

The worker must be enrolled, authorized, healthy, and verified before use.
"""

from datetime import UTC, datetime


class AndroidWorkerExecutor:
    executor_id = "android_worker_executor"
    capabilities = ("android_worker",)

    def health_check(self):
        return {
            "executor_id": self.executor_id,
            "status": "PENDING_WORKER",
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
            "status": "PENDING_DEVICE_VERIFICATION",
            "timestamp": datetime.now(UTC).isoformat(),
        }
