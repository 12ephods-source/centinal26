"""AREOP v1.0 deterministic ledger/state replay kernel."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .gates import validate_claim_status_transition, validate_event


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def state_hash(state) -> str:
    return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_ledger(path):
    events = []
    text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {lineno}: {exc}") from exc
    return events


def apply_event(state, event):
    nxt = copy.deepcopy(state)
    kind = event["kind"]
    p = event["payload"]

    if kind == "SET_OBJECTIVE":
        nxt["objective"] = p["objective"]
    elif kind == "SET_BOTTLENECK":
        nxt["active_bottleneck"] = p["value"]
    elif kind == "SET_NEXT_TEST":
        nxt["next_decisive_test"] = p["value"]
    elif kind == "UPSERT_CLAIM":
        cid = p["claim_id"]
        if cid in nxt["claims"]:
            raise ValueError(f"claim already exists: {cid}")
        nxt["claims"][cid] = {
            "claim": p["claim"],
            "status": p.get("status", "UNKNOWN"),
            "dependencies": sorted(set(p.get("dependencies", []))),
            "invalidation_conditions": p.get("invalidation_conditions", []),
            "evidence_ids": [event["event_id"]],
        }
    elif kind == "SET_CLAIM_STATUS":
        cid = p["claim_id"]
        if cid not in nxt["claims"]:
            raise ValueError(f"unknown claim: {cid}")
        old = nxt["claims"][cid]["status"]
        validate_claim_status_transition(old, p["status"])
        nxt["claims"][cid]["status"] = p["status"]
        nxt["claims"][cid]["evidence_ids"].append(event["event_id"])
    elif kind == "INVALIDATE_DEPENDENTS":
        source = p["claim_id"]
        target_status = p.get("status", "INDETERMINATE")
        for cid, claim in sorted(nxt["claims"].items()):
            if source in claim.get("dependencies", []):
                validate_claim_status_transition(claim["status"], target_status)
                claim["status"] = target_status
                claim["evidence_ids"].append(event["event_id"])
    elif kind == "REGISTER_ARTIFACT":
        aid = p["artifact_id"]
        if aid in nxt["artifacts"]:
            raise ValueError(f"artifact already exists: {aid}")
        nxt["artifacts"][aid] = {k: p[k] for k in sorted(p) if k != "artifact_id"}
    elif kind == "SET_TERMINAL":
        nxt["terminal_state"] = p["value"]
    else:
        raise ValueError(f"unknown event kind: {kind}")

    nxt["revision"] = state["revision"] + 1
    return nxt


def replay(initial_state, events):
    state = copy.deepcopy(initial_state)
    seen = set()
    for expected_seq, event in enumerate(events, 1):
        validate_event(event, expected_seq)
        eid = event["event_id"]
        if eid in seen:
            raise ValueError(f"duplicate event_id: {eid}")
        seen.add(eid)
        state = apply_event(state, event)
    return state


def replay_files(initial_state_path, ledger_path):
    return replay(load_json(initial_state_path), load_ledger(ledger_path))


def gate0(initial_state, events, materialized_state=None):
    a = replay(initial_state, events)
    b = replay(initial_state, events)
    if state_hash(a) != state_hash(b):
        return {"gate": "GATE-0", "status": "FAIL", "reason": "non-deterministic replay"}
    if materialized_state is not None and state_hash(a) != state_hash(materialized_state):
        return {"gate": "GATE-0", "status": "FAIL", "reason": "materialized state mismatch"}
    return {"gate": "GATE-0", "status": "PASS", "state_hash": state_hash(a), "revision": a["revision"]}
