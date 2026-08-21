"""Automation OS bounded queue worker scaffold.

This module defines the interface for processing verified tasks.
It does not execute external actions without an authorized worker.
"""

from datetime import UTC, datetime


def create_task_record(task_id, payload):
    return {
        "task_id": task_id,
        "payload": payload,
        "state": "QUEUED",
        "created_at": datetime.now(UTC).isoformat(),
    }


def process_task(task):
    if task.get("state") != "QUEUED":
        return {"status": "SKIPPED", "reason": "invalid_state"}

    return {
        "task_id": task.get("task_id"),
        "status": "PENDING_EXECUTOR",
        "verification_required": True,
    }
