"""
Frost Automation OS - Device Inventory Importer v1

Purpose:
Normalize phone application inventory exports into capability classification inputs.

Boundary:
This module parses inventory data. It does not install apps, grant permissions,
or activate agents.
"""

import json
from pathlib import Path
from datetime import datetime, timezone


def load_inventory(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def normalize_package(package_line):
    package = package_line
    if package.startswith("package:"):
        package = package[len("package:"):]
    return package.strip()


def create_records(packages, device_id):
    return {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "applications": [
            {
                "package": normalize_package(p),
                "classification_status": "pending"
            }
            for p in packages
        ]
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory")
    parser.add_argument("device_id")
    parser.add_argument("output")
    args = parser.parse_args()

    result = create_records(load_inventory(args.inventory), args.device_id)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
