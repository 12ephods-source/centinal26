"""Android inventory collector scaffold for Automation OS.

Collects locally supplied Android inventory data and normalizes it for the
capability pipeline. It does not bypass permissions or access restricted data.
"""

import json
from datetime import datetime, timezone


def collect_inventory(device_id, packages=None):
    return {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "packages": packages or [],
        "status": "PENDING_VERIFICATION",
    }


def save_inventory(path, inventory):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(inventory, handle, indent=2)


if __name__ == "__main__":
    print(json.dumps(collect_inventory("UNKNOWN_DEVICE"), indent=2))
