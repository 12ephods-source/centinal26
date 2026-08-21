"""Executor implementation template.

Executors perform bounded work assigned by the runtime layer.
Scheduling, authorization, and verification remain separate concerns.
"""

from datetime import UTC, datetime


class ExecutorTemplate:
    executor_id = "template_executor"
    capabilities = ()

    def health_check(self):
        return {
            "executor_id": self.executor_id,
            "status": "UNKNOWN",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def can_execute(self, request):
        return request.get("capability_id") in self.capabilities

    def execute(self, request):
        if not self.can_execute(request):
            return {
                "status": "REJECTED",
                "reason": "capability_not_supported",
            }

        return {
            "status": "PENDING_IMPLEMENTATION",
            "executor_id": self.executor_id,
        }
