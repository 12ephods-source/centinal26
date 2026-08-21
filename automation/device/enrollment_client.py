"""Frost Automation OS device enrollment client scaffold.

Generates a device enrollment record. It does not grant permissions or
activate a worker without verification.
"""

import json
from datetime import datetime, timezone


def create_enrollment(device_id, device_type, capabilities=None):
    return {
        "device_id": device_id,
        "device_type": device_type,
        "capabilities": capabilities or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "PENDING_VERIFICATION"
    }


if __name__ == "__main__":
    print(json.dumps(create_enrollment("UNKNOWN", "UNKNOWN"), indent=2))
