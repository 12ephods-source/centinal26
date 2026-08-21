"""Frost Automation OS scheduler scaffold.

Creates bounded task scheduling primitives.
No task is executed without verification and authorization.
"""

from datetime import datetime, timezone


def create_task(goal, priority="normal"):
    return {
        "goal": goal,
        "priority": priority,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    print(create_task("initialize"))
