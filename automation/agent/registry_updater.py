"""
Frost Automation OS - Agent Registry Updater v1.1

Consumes classified capability records and prepares registry candidates.
No automatic trust promotion is performed.

Rules:
- Preserve provenance.
- Avoid duplicate agent identities.
- Keep verification separate from registration.
"""

import json
from datetime import UTC, datetime
from pathlib import Path


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
                    "timestamp": datetime.now(UTC).isoformat()
                }
            }

    registry["agents"] = list(existing.values())
    Path(registry_file).write_text(json.dumps(registry, indent=2))
    return registry


if __name__ == "__main__":
    print("Registry updater module ready.")
