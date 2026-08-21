"""Frost Automation OS agent registry updater.

Consumes classified capability records and prepares registry candidates.
No automatic trust promotion is performed.
"""

import json
from pathlib import Path
from datetime import datetime, timezone


def update_registry(classified_file, registry_file):
    classified = json.loads(Path(classified_file).read_text())
    registry = json.loads(Path(registry_file).read_text())

    existing = {a.get("package"): a for a in registry.get("agents", [])}

    for app in classified.get("applications", []):
        package = app.get("package")
        if package and package not in existing:
            existing[package] = {
                "package": package,
                "capabilities": app.get("capabilities", []),
                "verification_status": "pending",
                "provenance": {
                    "source": classified_file,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

    registry["agents"] = list(existing.values())
    Path(registry_file).write_text(json.dumps(registry, indent=2))


if __name__ == "__main__":
    print("Registry updater module ready.")
