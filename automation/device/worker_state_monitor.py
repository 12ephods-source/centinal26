"""Worker state monitor scaffold for Automation OS.

Tracks worker heartbeat freshness and lifecycle state.
"""

from datetime import UTC, datetime

ONLINE_WINDOW_SECONDS = 300


def evaluate_worker_state(last_heartbeat):
    if not last_heartbeat:
        return "UNKNOWN"

    now = datetime.now(UTC)
    age = (now - last_heartbeat).total_seconds()

    if age <= ONLINE_WINDOW_SECONDS:
        return "ONLINE"

    return "OFFLINE"


if __name__ == "__main__":
    print({"status": "READY", "verification": "PENDING"})
