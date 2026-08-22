from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from canonical_store import CanonicalStore
from structured_semantic_dedupe import StructuredSemanticError, enrich_bundle
from validate_canonical_kernel import validate_bundle


def _claim(
    object_id: str,
    *,
    value: object,
    statement: str,
    comparison_mode: str | None = "EXCLUSIVE_VALUE",
    structured: bool = True,
) -> dict:
    payload: dict[str, object] = {"statement": statement}
    if structured:
        payload.update(
            {
                "subject_ids": ["device:alpha"],
                "predicate": "security_state",
                "object_value": value,
            }
        )
        if comparison_mode is not None:
            payload["comparison_mode"] = comparison_mode
    suffix = object_id.removeprefix("obj_")
    digit = (sum(ord(char) for char in suffix) % 15) + 1
    return {
        "object_id": object_id,
        "schema_version": "1.0.0",
        "type": "CLAIM",
        "subtype": None,
        "content_hash": f"sha256:{digit:x}" * 0 + "sha256:" + f"{digit:x}" * 64,
        "identity_hash": None,
        "created_at": "2026-08-22T17:30:00Z",
        "observed_at": "2026-08-22T17:30:00Z",
        "ingested_at": "2026-08-22T17:30:01Z",
        "modified_at_source": None,
        "source_id": "test",
        "parent_ids": [],
        "related_ids": [],
        "status": "CANONICAL",
        "epistemic_status": "OBSERVED",
        "verification_status": "UNVERIFIED",
        "confidence": 1.0,
        "authority_class": "AUTHORITATIVE_RECORD",
        "authoritative": True,
        "provenance_ids": [],
        "tag_ids": [],
        "project_ids": ["dedupe-organizer"],
        "payload": payload,
        "extensions": {},
    }


def _bundle() -> dict:
    return {
        "objects": [
            _claim("obj_claim_a", value="SAFE", statement="alpha is safe"),
            _claim("obj_claim_b", value="SAFE", statement="different wording, same fields"),
            _claim("obj_claim_c", value="COMPROMISED", statement="alpha is compromised"),
        ],
        "provenance_events": [],
        "filter_decisions": [],
    }


def _derived(enriched: dict, object_type: str) -> list[dict]:
    return [obj for obj in enriched["objects"] if obj.get("type") == object_type]


def test_structured_equivalence_creates_duplicate_group() -> None:
    enriched = enrich_bundle(_bundle())
    groups = _derived(enriched, "DUPLICATE_GROUP")
    assert len(groups) == 1
    payload = groups[0]["payload"]
    assert payload["member_ids"] == ["obj_claim_a", "obj_claim_b"]
    assert payload["duplicate_type"] == "STRUCTURED_SEMANTIC"
    assert payload["deletion_authority"] is False
    assert groups[0]["authoritative"] is False


def test_explicit_exclusive_disagreement_creates_unresolved_contradiction() -> None:
    enriched = enrich_bundle(_bundle())
    conflicts = _derived(enriched, "CONTRADICTION")
    assert len(conflicts) == 1
    payload = conflicts[0]["payload"]
    assert payload["member_ids"] == ["obj_claim_a", "obj_claim_b", "obj_claim_c"]
    assert payload["object_values"] == ["COMPROMISED", "SAFE"]
    assert payload["resolution_status"] == "UNRESOLVED"
    assert payload["winner_id"] is None


def test_nonexclusive_values_are_not_silently_called_contradictions() -> None:
    bundle = {
        "objects": [
            _claim("obj_claim_a", value="A", statement="a", comparison_mode=None),
            _claim("obj_claim_b", value="B", statement="b", comparison_mode=None),
        ],
        "provenance_events": [],
        "filter_decisions": [],
    }
    enriched = enrich_bundle(bundle)
    assert not _derived(enriched, "CONTRADICTION")


def test_unstructured_free_text_is_not_guessed_semantically() -> None:
    bundle = {
        "objects": [
            _claim("obj_claim_a", value="ignored", statement="same text", structured=False),
            _claim("obj_claim_b", value="ignored", statement="same text", structured=False),
        ],
        "provenance_events": [],
        "filter_decisions": [],
    }
    enriched = enrich_bundle(bundle)
    assert len(enriched["objects"]) == 2
    assert not enriched["provenance_events"]


def test_derived_bundle_satisfies_canonical_kernel() -> None:
    enriched = enrich_bundle(_bundle())
    assert validate_bundle(enriched) == []
    for obj in _derived(enriched, "DUPLICATE_GROUP") + _derived(enriched, "CONTRADICTION"):
        assert obj["provenance_ids"]
        assert obj["epistemic_status"] == "DERIVED"
        assert obj["verification_status"] == "UNVERIFIED"


def test_enrichment_is_idempotent() -> None:
    once = enrich_bundle(_bundle())
    twice = enrich_bundle(once)
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)


def test_generated_relationship_ids_are_input_order_invariant() -> None:
    original = _bundle()
    reversed_bundle = copy.deepcopy(original)
    reversed_bundle["objects"].reverse()
    first = enrich_bundle(original)
    second = enrich_bundle(reversed_bundle)
    first_ids = sorted(
        obj["object_id"]
        for obj in first["objects"]
        if obj["type"] in {"DUPLICATE_GROUP", "CONTRADICTION"}
    )
    second_ids = sorted(
        obj["object_id"]
        for obj in second["objects"]
        if obj["type"] in {"DUPLICATE_GROUP", "CONTRADICTION"}
    )
    assert first_ids == second_ids


def test_output_introduces_no_filter_or_deletion_decision() -> None:
    enriched = enrich_bundle(_bundle())
    assert enriched["filter_decisions"] == []
    serialized = json.dumps(enriched, sort_keys=True)
    assert '"decision": "DELETE"' not in serialized


def test_enriched_bundle_roundtrips_through_canonical_store() -> None:
    source = _bundle()
    enriched = enrich_bundle(source)
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "canonical.db"
        with CanonicalStore(db) as store:
            first = store.ingest_bundle(source)
            second = store.ingest_bundle(enriched)
            third = store.ingest_bundle(enriched)
            assert first["objects"] == 3
            assert second["objects"] == 2
            assert second["provenance_events"] == 2
            assert third == {"objects": 0, "provenance_events": 0, "filter_decisions": 0}
            assert store.stats()["canonical_objects"] == 5


def test_invalid_source_bundle_fails_before_derivation() -> None:
    broken = _bundle()
    broken["objects"][0]["epistemic_status"] = "DERIVED"
    with pytest.raises(StructuredSemanticError, match="input bundle invariant failure"):
        enrich_bundle(broken)
