from __future__ import annotations

import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

from centinal26.intent_execution import CapabilityRegistry, IntentExecutionController

from centinal26.event_state import EventStore
from centinal26.physical_capabilities import register_physical_capabilities


def main() -> int:
    evidence_dir = Path(os.environ.get("CENTINAL26_EVIDENCE_DIR", "./physical-evidence")).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    store = EventStore(evidence_dir / "intent-events.sqlite3")
    registry = CapabilityRegistry()
    register_physical_capabilities(registry)
    controller = IntentExecutionController(store, registry)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    results = []
    try:
        for index, capability in enumerate(("device.python_version", "device.uname"), start=1):
            result = controller.ingest_and_execute(
                text="Proceed", adapter_id="termux-physical-gate",
                external_id=f"{run_id}-{index}", capability=capability,
                payload={}, actor="physical-gate",
            )
            results.append(result.as_dict())
        passed = all(item["completed"] and item["verified"] for item in results)
        report = {
            "schema": "centinal26.physical_intent_gate.v1", "run_id": run_id,
            "platform": platform.platform(), "python": sys.version, "results": results,
            "event_chain_valid": store.verify_chain(), "status": "PASS" if passed else "FAIL",
        }
        path = evidence_dir / f"PHYSICAL_INTENT_GATE_{run_id}.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(path)
        print(report["status"])
        return 0 if passed and report["event_chain_valid"] else 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
