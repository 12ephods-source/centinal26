"""Automation OS regression checks."""

import json
from pathlib import Path


def check_json(path):
    with open(path, "r", encoding="utf-8") as f:
        json.load(f)
    return True


def run_checks(root="."):
    root = Path(root)
    required = [
        "automation/agent/registry.json",
        "automation/device/device_registry.json",
        "automation/controller/task_queue.json",
        "automation/execution/audit_ledger.json",
    ]
    results = {}
    for item in required:
        p = root / item
        results[item] = p.exists() and check_json(p) if p.exists() else False
    return results


if __name__ == "__main__":
    print(json.dumps(run_checks(), indent=2))
