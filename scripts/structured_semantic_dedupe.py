"""Deterministic structured-claim dedupe and contradiction derivation.

This module intentionally does not perform free-text semantic inference. It derives
only from explicit structured claim fields and emits provenance-linked, non-authoritative
objects. Duplicate detection never authorizes deletion or mutation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from canonical_store import CanonicalStore, CanonicalStoreError
from validate_canonical_kernel import validate_bundle

TOOL_VERSION = "1"
RULE_ID = "structured-claim-v1"
EXCLUSIVE_MODE = "EXCLUSIVE_VALUE"


class StructuredSemanticError(RuntimeError):
    """Raised when structured semantic derivation cannot proceed safely."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> str:
    return f"sha256:{_digest(value)}"


def _claim_fields(obj: dict[str, Any]) -> tuple[tuple[str, ...], str, Any] | None:
    if obj.get("type") != "CLAIM":
        return None
    payload = obj.get("payload")
    if not isinstance(payload, dict):
        return None
    subjects = payload.get("subject_ids")
    predicate = payload.get("predicate")
    if (
        not isinstance(subjects, list)
        or not subjects
        or not all(isinstance(item, str) and item for item in subjects)
        or not isinstance(predicate, str)
        or not predicate
        or "object_value" not in payload
    ):
        return None
    return tuple(sorted(set(subjects))), predicate, payload["object_value"]


def _stable_time(members: list[dict[str, Any]]) -> str:
    times = [
        str(obj.get("ingested_at") or obj.get("created_at") or "1970-01-01T00:00:00Z")
        for obj in members
    ]
    return max(times)


def _project_ids(members: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            project_id
            for obj in members
            for project_id in obj.get("project_ids", [])
            if isinstance(project_id, str) and project_id
        }
    )


def _derived_object(
    *,
    object_type: str,
    subtype: str,
    object_id: str,
    payload: dict[str, Any],
    member_ids: list[str],
    provenance_id: str,
    members: list[dict[str, Any]],
    identity_material: Any,
) -> dict[str, Any]:
    timestamp = _stable_time(members)
    return {
        "object_id": object_id,
        "schema_version": "1.0.0",
        "type": object_type,
        "subtype": subtype,
        "content_hash": _sha256({"type": object_type, "subtype": subtype, "payload": payload}),
        "identity_hash": _sha256(identity_material),
        "created_at": timestamp,
        "observed_at": None,
        "ingested_at": timestamp,
        "modified_at_source": None,
        "source_id": None,
        "parent_ids": member_ids,
        "related_ids": member_ids,
        "status": "CANONICAL",
        "epistemic_status": "DERIVED",
        "verification_status": "UNVERIFIED",
        "confidence": 1.0,
        "authority_class": "DERIVED_RECORD",
        "authoritative": False,
        "provenance_ids": [provenance_id],
        "tag_ids": [],
        "project_ids": _project_ids(members),
        "payload": payload,
        "extensions": {
            "semantic_scope": "STRUCTURED_FIELDS_ONLY",
            "free_text_inference": False,
            "mutation_authority": "NONE",
        },
    }


def _provenance_event(
    *,
    provenance_id: str,
    member_ids: list[str],
    output_id: str,
    operation: str,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "provenance_event_id": provenance_id,
        "input_ids": member_ids,
        "operation": operation,
        "tool_id": "structured_semantic_dedupe",
        "tool_version": TOOL_VERSION,
        "rule_id": RULE_ID,
        "parameters": {
            "semantic_scope": "STRUCTURED_FIELDS_ONLY",
            "comparison_mode_required_for_contradiction": EXCLUSIVE_MODE,
        },
        "output_ids": [output_id],
        "timestamp": timestamp,
        "operator": "deterministic-rule",
        "deterministic": True,
    }


def _append_exact_or_fail(items: list[dict[str, Any]], candidate: dict[str, Any], id_key: str) -> None:
    candidate_id = candidate[id_key]
    for existing in items:
        if existing.get(id_key) == candidate_id:
            if _canonical_json(existing) != _canonical_json(candidate):
                raise StructuredSemanticError(
                    f"stable derived id {candidate_id} already exists with different content"
                )
            return
    items.append(candidate)


def enrich_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Return an enriched canonical bundle with deterministic derived relationships."""
    errors = validate_bundle(bundle)
    if errors:
        raise StructuredSemanticError("input bundle invariant failure: " + "; ".join(errors))

    enriched = copy.deepcopy(bundle)
    objects = enriched.setdefault("objects", [])
    provenance = enriched.setdefault("provenance_events", [])
    enriched.setdefault("filter_decisions", [])

    claims: list[tuple[dict[str, Any], tuple[str, ...], str, Any]] = []
    for obj in bundle.get("objects", []):
        fields = _claim_fields(obj)
        if fields is not None:
            subjects, predicate, object_value = fields
            claims.append((obj, subjects, predicate, object_value))

    duplicate_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contradiction_contexts: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for obj, subjects, predicate, object_value in claims:
        duplicate_key = _canonical_json(
            {"subject_ids": subjects, "predicate": predicate, "object_value": object_value}
        )
        duplicate_groups[duplicate_key].append(obj)
        payload = obj["payload"]
        if payload.get("comparison_mode") == EXCLUSIVE_MODE:
            context_key = _canonical_json({"subject_ids": subjects, "predicate": predicate})
            contradiction_contexts[context_key].append(obj)

    for semantic_key, members in sorted(duplicate_groups.items()):
        if len(members) < 2:
            continue
        members = sorted(members, key=lambda item: item["object_id"])
        member_ids = [item["object_id"] for item in members]
        digest = _digest({"kind": "duplicate", "key": semantic_key, "members": member_ids})
        object_id = f"obj_duplicate_{digest[:24]}"
        provenance_id = f"prov_duplicate_{digest[:24]}"
        fields = _claim_fields(members[0])
        assert fields is not None
        subjects, predicate, object_value = fields
        payload = {
            "member_ids": member_ids,
            "duplicate_type": "STRUCTURED_SEMANTIC",
            "subject_ids": list(subjects),
            "predicate": predicate,
            "object_value": object_value,
            "resolution_status": "UNRESOLVED",
            "deletion_authority": False,
        }
        candidate = _derived_object(
            object_type="DUPLICATE_GROUP",
            subtype="STRUCTURED_CLAIM_DUPLICATE",
            object_id=object_id,
            payload=payload,
            member_ids=member_ids,
            provenance_id=provenance_id,
            members=members,
            identity_material={"kind": "duplicate", "key": semantic_key},
        )
        event = _provenance_event(
            provenance_id=provenance_id,
            member_ids=member_ids,
            output_id=object_id,
            operation="DETECT_STRUCTURED_SEMANTIC_DUPLICATE",
            timestamp=candidate["created_at"],
        )
        _append_exact_or_fail(objects, candidate, "object_id")
        _append_exact_or_fail(provenance, event, "provenance_event_id")

    for context_key, members in sorted(contradiction_contexts.items()):
        values: dict[str, Any] = {}
        for member in members:
            fields = _claim_fields(member)
            assert fields is not None
            values[_canonical_json(fields[2])] = fields[2]
        if len(values) < 2:
            continue
        members = sorted(members, key=lambda item: item["object_id"])
        member_ids = [item["object_id"] for item in members]
        value_items = [values[key] for key in sorted(values)]
        digest = _digest(
            {"kind": "contradiction", "context": context_key, "members": member_ids}
        )
        object_id = f"obj_contradiction_{digest[:24]}"
        provenance_id = f"prov_contradiction_{digest[:24]}"
        fields = _claim_fields(members[0])
        assert fields is not None
        subjects, predicate, _ = fields
        payload = {
            "member_ids": member_ids,
            "subject_ids": list(subjects),
            "predicate": predicate,
            "object_values": value_items,
            "comparison_mode": EXCLUSIVE_MODE,
            "resolution_status": "UNRESOLVED",
            "winner_id": None,
        }
        candidate = _derived_object(
            object_type="CONTRADICTION",
            subtype="EXCLUSIVE_STRUCTURED_CLAIM_CONFLICT",
            object_id=object_id,
            payload=payload,
            member_ids=member_ids,
            provenance_id=provenance_id,
            members=members,
            identity_material={"kind": "contradiction", "context": context_key},
        )
        event = _provenance_event(
            provenance_id=provenance_id,
            member_ids=member_ids,
            output_id=object_id,
            operation="DETECT_EXCLUSIVE_STRUCTURED_CLAIM_CONTRADICTION",
            timestamp=candidate["created_at"],
        )
        _append_exact_or_fail(objects, candidate, "object_id")
        _append_exact_or_fail(provenance, event, "provenance_event_id")

    output_errors = validate_bundle(enriched)
    if output_errors:
        raise StructuredSemanticError("derived bundle invariant failure: " + "; ".join(output_errors))
    return enriched


def _load_bundle(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StructuredSemanticError(f"cannot read input bundle: {exc}") from exc
    if not isinstance(payload, dict):
        raise StructuredSemanticError("input bundle root must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()

    try:
        enriched = enrich_bundle(_load_bundle(args.input))
        if args.output:
            args.output.write_text(json.dumps(enriched, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.db:
            with CanonicalStore(args.db) as store:
                result = store.ingest_bundle(enriched)
            print(json.dumps({"ingest": result}, sort_keys=True))
        elif not args.output:
            print(json.dumps(enriched, indent=2, sort_keys=True))
    except (StructuredSemanticError, CanonicalStoreError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
