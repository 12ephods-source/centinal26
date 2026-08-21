"""Worker heartbeat reporter scaffold."""
import json
from datetime import datetime, timezone


def create_heartbeat(device_id: str, status: str = "UNKNOWN"):
    return {
        "device_id": device_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verification_status": "PENDING"
    }


if __name__ == "__main__":
    print(json.dumps(create_heartbeat("UNREGISTERED"), indent=2))
