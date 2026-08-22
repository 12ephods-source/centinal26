"""Bounded improvement-cycle reconciler for the Centinal26 Termux daemon.

This module never grants authority or executes model-suggested commands. It inspects
recent durable task/evidence state, identifies recoverable failure classes, and emits a
machine-readable observation/critique/recommendation record.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

ROOT = Path(os.environ.get("CENTINAL26_HOME", str(Path.home() / ".centinal26")))
DB = ROOT / "state" / "daemon.sqlite3"
OUT = ROOT / "state" / "improvement_cycle.jsonl"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    if not DB.exists():
        print(json.dumps({"status": "NO_STATE"}))
        return 0
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in con.execute(
            "SELECT id,intent,capability,state,attempt_count,last_error,updated_at "
            "FROM task ORDER BY updated_at DESC LIMIT 50"
        )
    ]
    failed = [row for row in rows if row["state"] in {"FAILED", "RETRY_WAIT"}]
    blocked = [
        row
        for row in rows
        if row["state"] not in {"VERIFIED", "FAILED", "RETRY_WAIT", "QUEUED", "RUNNING"}
    ]
    recommendations = []
    for row in failed:
        error = (row.get("last_error") or "").lower()
        if "not configured" in error or "authentication" in error or "credential" in error:
            recommendations.append(
                {
                    "task_id": row["id"],
                    "action": "preserve_blocker_and_try_independent_work",
                    "reason": "authorization_or_configuration_boundary",
                }
            )
        elif row["attempt_count"] < 5:
            recommendations.append(
                {
                    "task_id": row["id"],
                    "action": "allow_existing_bounded_retry",
                    "reason": "retry_budget_available",
                }
            )
        else:
            recommendations.append(
                {
                    "task_id": row["id"],
                    "action": "preserve_failure_and_select_alternate_capability_if_policy_allows",
                    "reason": "retry_budget_exhausted",
                }
            )
    record = {
        "ts": int(time.time()),
        "cycle": [
            "observe_measure",
            "analyze",
            "hypothesize",
            "compare_approaches",
            "criticize",
            "improve",
            "implement",
            "test",
            "independently_verify",
            "record_evidence",
            "update_canonical_state",
            "repeat",
        ],
        "observed_tasks": len(rows),
        "failed_or_retrying": len(failed),
        "other_blocked": len(blocked),
        "recommendations": recommendations,
        "authority_note": "recommendations cannot widen capabilities or self-certify device-tested/production-ready",
    }
    record["sha256"] = digest(record)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
