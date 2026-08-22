#!/usr/bin/env python3
"""Semantic invariant validator for the Dedupe/Organizer canonical kernel.

Uses only the Python standard library. JSON Schema files document structure;
this validator enforces cross-object invariants that JSON Schema alone cannot.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ALLOWED_FILTER_DECISIONS = {
    "RETAIN", "REJECT_FROM_PROJECTION", "MERGE", "QUARANTINE", "DEFER", "PROMOTE"
}
DERIVED_EPISTEMIC = {"DERIVED", "INFERENCE", "SPECULATION", "PREDICTION"}


def _err(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_bundle(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    objects = bundle.get("objects", [])
    provenance = bundle.get("provenance_events", [])
    filter_decisions = bundle.get("filter_decisions", [])

    if not isinstance(objects, list):
        return ["objects must be a list"]
    if not isinstance(provenance, list):
        return ["provenance_events must be a list"]
    if not isinstance(filter_decisions, list):
        return ["filter_decisions must be a list"]

    object_by_id: dict[str, dict[str, Any]] = {}
    seen_content: dict[str, str] = {}
    for i, obj in enumerate(objects):
        if not isinstance(obj, dict):
            _err(errors, f"objects[{i}] must be an object")
            continue
        oid = obj.get("object_id")
        if not isinstance(oid, str) or not oid:
            _err(errors, f"objects[{i}] missing object_id")
            continue
        ch = obj.get("content_hash")
        if not isinstance(ch, str) or not SHA256_RE.match(ch):
            _err(errors, f"{oid}: invalid content_hash")
        if oid in seen_content and seen_content[oid] != ch:
            _err(errors, f"{oid}: immutable object_id reused with different content_hash")
        else:
            seen_content[oid] = ch
        object_by_id.setdefault(oid, obj)

        authority = obj.get("authority_class")
        authoritative = obj.get("authoritative")
        if authority == "PROJECTION" and authoritative is not False:
            _err(errors, f"{oid}: projections must declare authoritative=false")
        if authority == "AUTHORITATIVE_RECORD" and authoritative is not True:
            _err(errors, f"{oid}: authoritative records must declare authoritative=true")
        if authority == "DERIVED_RECORD" and authoritative is not False:
            _err(errors, f"{oid}: derived records must declare authoritative=false")

        prov_ids = obj.get("provenance_ids", [])
        if not isinstance(prov_ids, list):
            _err(errors, f"{oid}: provenance_ids must be a list")
            prov_ids = []
        if obj.get("epistemic_status") in DERIVED_EPISTEMIC or authority in {"DERIVED_RECORD", "PROJECTION"}:
            if not prov_ids:
                _err(errors, f"{oid}: derived/projection object requires provenance")

        payload = obj.get("payload")
        if not isinstance(payload, dict):
            _err(errors, f"{oid}: payload must be an object")
            payload = {}

        if obj.get("type") == "CLAIM" and obj.get("verification_status") == "VERIFIED":
            evidence_ids = payload.get("evidence_ids", [])
            if not isinstance(evidence_ids, list) or not evidence_ids:
                _err(errors, f"{oid}: VERIFIED claim requires evidence_ids")

        if obj.get("type") == "RECONSTRUCTION":
            originality = payload.get("originality_status")
            if originality in {"ORIGINAL", "AUTHENTIC_ORIGINAL"}:
                _err(errors, f"{oid}: reconstructed object cannot claim original status")
            if not prov_ids:
                _err(errors, f"{oid}: reconstruction requires provenance")

    prov_by_id: dict[str, dict[str, Any]] = {}
    for i, event in enumerate(provenance):
        if not isinstance(event, dict):
            _err(errors, f"provenance_events[{i}] must be an object")
            continue
        pid = event.get("provenance_event_id")
        if not isinstance(pid, str) or not pid:
            _err(errors, f"provenance_events[{i}] missing provenance_event_id")
            continue
        if pid in prov_by_id:
            _err(errors, f"duplicate provenance_event_id: {pid}")
        prov_by_id[pid] = event
        inputs = event.get("input_ids", [])
        outputs = event.get("output_ids", [])
        if not inputs:
            _err(errors, f"{pid}: provenance event requires at least one input")
        if not outputs:
            _err(errors, f"{pid}: provenance event requires at least one output")
        for ref in inputs:
            if ref not in object_by_id:
                _err(errors, f"{pid}: unresolved input object {ref}")
        for ref in outputs:
            if ref not in object_by_id:
                _err(errors, f"{pid}: unresolved output object {ref}")

    for oid, obj in object_by_id.items():
        for pid in obj.get("provenance_ids", []):
            event = prov_by_id.get(pid)
            if event is None:
                _err(errors, f"{oid}: unresolved provenance event {pid}")
            elif oid not in event.get("output_ids", []):
                _err(errors, f"{oid}: provenance event {pid} does not name object as output")

    for i, decision in enumerate(filter_decisions):
        if not isinstance(decision, dict):
            _err(errors, f"filter_decisions[{i}] must be an object")
            continue
        did = decision.get("filter_decision_id", f"filter_decisions[{i}]")
        action = decision.get("decision")
        if action not in ALLOWED_FILTER_DECISIONS:
            _err(errors, f"{did}: illegal dedupe/filter decision {action!r}; deletion is not a canonicalization action")
        input_id = decision.get("input_object_id")
        if input_id not in object_by_id:
            _err(errors, f"{did}: unresolved input_object_id {input_id}")
        if action == "MERGE" and not decision.get("canonical_target_id"):
            _err(errors, f"{did}: MERGE requires canonical_target_id")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.bundle.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL: cannot read JSON bundle: {exc}", file=sys.stderr)
        return 2
    errors = validate_bundle(data)
    if errors:
        print("FAIL")
        for e in errors:
            print(f"- {e}")
        return 1
    print("PASS: canonical kernel invariants satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
