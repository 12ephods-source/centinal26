"""Automation OS inventory pipeline.

Transforms device inventory records into capability-ready records.
"""

from datetime import datetime, timezone


def normalize_inventory(record):
    return {
        "device_id": record.get("device_id", "UNKNOWN"),
        "applications": record.get("applications", []),
        "normalized_at": datetime.now(timezone.utc).isoformat(),
        "status": "PENDING_CLASSIFICATION",
    }


def build_capability_input(inventory):
    return {
        "device_id": inventory["device_id"],
        "candidates": [
            {
                "package": app.get("package"),
                "classification_status": "PENDING",
            }
            for app in inventory.get("applications", [])
        ],
        "verification_status": "PENDING",
    }


if __name__ == "__main__":
    sample = {"device_id": "PHONE-UNKNOWN", "applications": []}
    print(build_capability_input(normalize_inventory(sample)))
