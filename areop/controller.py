"""AREOP v1.0 deterministic, tamper-evident ledger/state replay kernel."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

from .gates import validate_claim_status_transition, validate_event

GENESIS_HASH = "0" * 64


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_obj(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def state_hash(state) -> str:
    return sha256_obj(state)


def event_hash(event) -> str:
    body = {k: v for k, v in event.items() if k != "event_hash"}
    return sha256_obj(body)


def seal_event(event, prev_hash=GENESIS_HASH):
    sealed = copy.deepcopy(event)
    sealed["prev_event_hash"] = prev_hash
    sealed["event_hash"] = event_hash(sealed)
    return sealed


def seal_events(events):
    out, prev = [], GENESIS_HASH
    for event in events:
        sealed = seal_event(event, prev)
        out.append(sealed)
        prev = sealed["event_hash"]
    return out


def verify_chain(events):
    prev = GENESIS_HASH
    for event in events:
        if "event_hash" not in event or "prev_event_hash" not in event:
            raise ValueError("unsealed evidence event")
        if event["prev_event_hash"] != prev:
            raise ValueError("evidence hash-chain discontinuity")
        if event_hash(event) != event["event_hash"]:
            raise ValueError("evidence event hash mismatch")
        prev = event["event_hash"]
    return prev


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


def append_event(path, event):
    """Durably append exactly one sealed evidence event; never rewrite history."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_ledger(path)
    if existing:
        verify_chain(existing)
    expected_seq = len(existing) + 1
    validate_event(event, expected_seq)
    if any(row["event_id"] == event["event_id"] for row in existing):
        raise ValueError(f"duplicate event_id: {event['event_id']}")
    prev = existing[-1]["event_hash"] if existing else GENESIS_HASH
    sealed = seal_event(event, prev)
    data = canonical_json(sealed) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    # Read-back verification is the commit postcondition.
    verify_chain(load_ledger(path))
    return sealed


def atomic_write_state(path, state):
    """Materialize disposable state atomically; ledger remains source of truth."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    if state_hash(json.loads(tmp.read_text(encoding="utf-8"))) != state_hash(state):
        tmp.unlink(missing_ok=True)
        raise RuntimeError("materialized-state verification failed")
    os.replace(tmp, path)


def apply_event(state, event):
    nxt = copy.deepcopy(state)
    kind, p = event["kind"], event["payload"]
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
            "claim": p["claim"], "status": p.get("status", "UNKNOWN"),
            "dependencies": sorted(set(p.get("dependencies", []))),
            "invalidation_conditions": p.get("invalidation_conditions", []),
            "evidence_ids": [event["event_id"]],
        }
    elif kind == "SET_CLAIM_STATUS":
        cid = p["claim_id"]
        if cid not in nxt["claims"]:
            raise ValueError(f"unknown claim: {cid}")
        validate_claim_status_transition(nxt["claims"][cid]["status"], p["status"])
        nxt["claims"][cid]["status"] = p["status"]
        nxt["claims"][cid]["evidence_ids"].append(event["event_id"])
    elif kind == "INVALIDATE_DEPENDENTS":
        source, target = p["claim_id"], p.get("status", "INDETERMINATE")
        for _, claim in sorted(nxt["claims"].items()):
            if source in claim.get("dependencies", []):
                validate_claim_status_transition(claim["status"], target)
                claim["status"] = target
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


def replay(initial_state, events, require_chain=False):
    if require_chain and events:
        verify_chain(events)
    state, seen = copy.deepcopy(initial_state), set()
    for expected_seq, event in enumerate(events, 1):
        validate_event(event, expected_seq)
        eid = event["event_id"]
        if eid in seen:
            raise ValueError(f"duplicate event_id: {eid}")
        seen.add(eid)
        state = apply_event(state, event)
    return state


def replay_files(initial_state_path, ledger_path):
    events = load_ledger(ledger_path)
    return replay(load_json(initial_state_path), events, require_chain=bool(events))


def gate0(initial_state, events, materialized_state=None):
    if events:
        verify_chain(events)
    a = replay(initial_state, events)
    b = replay(initial_state, events)
    if state_hash(a) != state_hash(b):
        return {"gate": "GATE-0", "status": "FAIL", "reason": "non-deterministic replay"}
    if materialized_state is not None and state_hash(a) != state_hash(materialized_state):
        return {"gate": "GATE-0", "status": "FAIL", "reason": "materialized state mismatch"}
    return {"gate": "GATE-0", "status": "PASS", "state_hash": state_hash(a), "revision": a["revision"]}
