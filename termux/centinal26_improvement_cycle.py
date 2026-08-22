#!/usr/bin/env python3
"""Bounded improvement-cycle reconciler for the Centinal26 Termux daemon.

This module never grants authority or executes model-suggested commands. It inspects
recent durable task/evidence state, identifies recoverable failure classes, emits a
machine-readable observation/critique/recommendation record, and may only requeue a
failed task when the existing capability and payload are unchanged and retry budget
remains available.
"""
from __future__ import annotations
import hashlib, json, os, sqlite3, time
from pathlib import Path

ROOT=Path(os.environ.get("CENTINAL26_HOME",str(Path.home()/".centinal26")))
DB=ROOT/"state"/"daemon.sqlite3"
OUT=ROOT/"state"/"improvement_cycle.jsonl"

def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def main():
    if not DB.exists():
        print(json.dumps({"status":"NO_STATE"})); return 0
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    rows=[dict(r) for r in c.execute("SELECT id,intent,capability,state,attempt_count,last_error,updated_at FROM task ORDER BY updated_at DESC LIMIT 50")]
    failed=[r for r in rows if r["state"] in {"FAILED","RETRY_WAIT"}]
    blocked=[r for r in rows if r["state"] not in {"VERIFIED","FAILED","RETRY_WAIT","QUEUED","RUNNING"}]
    recommendation=[]
    for r in failed:
        err=(r.get("last_error") or "").lower()
        if "not configured" in err or "authentication" in err or "credential" in err:
            recommendation.append({"task_id":r["id"],"action":"preserve_blocker_and_try_independent_work","reason":"authorization_or_configuration_boundary"})
        elif r["attempt_count"] < 5:
            recommendation.append({"task_id":r["id"],"action":"allow_existing_bounded_retry","reason":"retry_budget_available"})
        else:
            recommendation.append({"task_id":r["id"],"action":"preserve_failure_and_select_alternate_capability_if_policy_allows","reason":"retry_budget_exhausted"})
    rec={
      "ts":int(time.time()),
      "cycle":["observe_measure","analyze","hypothesize","compare_approaches","criticize","improve","implement","test","independently_verify","record_evidence","update_canonical_state","repeat"],
      "observed_tasks":len(rows),"failed_or_retrying":len(failed),"other_blocked":len(blocked),
      "recommendations":recommendation,
      "authority_note":"recommendations cannot widen capabilities or self-certify device-tested/production-ready"
    }
    rec["sha256"]=digest(rec)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("a") as f: f.write(json.dumps(rec,sort_keys=True)+"\n")
    print(json.dumps(rec,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
