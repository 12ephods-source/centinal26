"""Adversarial coverage for the standalone governance-bundle validator."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from centinal26.governance import (
    AUTH_FIELDS,
    BUNDLE_FIELDS,
    CLAIM_FIELDS,
    EVIDENCE_FIELDS,
    OPERATION_FIELDS,
    PROMOTION_FIELDS,
    TERMINAL_FIELDS,
    validate_bundle,
    validate_file,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


def valid_bundle() -> dict:
    return {
        "schema": "centinal26-governance-bundle-v1",
        "authorizations": [
            {
                "schema": "centinal26-authorization-v1",
                "authorization_id": "auth-1",
                "issuer": "human",
                "subject": "agent",
                "capability": "system.echo",
                "scope": {"resource": "echo"},
                "risk_class": "HIGH",
                "issued_at": "2026-08-21T11:00:00+00:00",
                "expires_at": "2026-08-21T13:00:00+00:00",
                "signature": "sig",
            }
        ],
        "evidence": [
            {
                "schema": "centinal26-governance-evidence-v1",
                "evidence_id": "ev-1",
                "sha256": DIGEST,
                "source_type": "SOURCE",
                "created_at": "2026-08-21T11:30:00+00:00",
                "immutable": True,
            }
        ],
        "operations": [
            {
                "schema": "centinal26-operation-v1",
                "operation_id": "op-1",
                "actor": "agent",
                "authorization_id": "auth-1",
                "capability_id": "system.echo",
                "scope": {"resource": "echo"},
                "risk_class": "HIGH",
                "preconditions": [],
                "postconditions": ["output verified"],
                "destructive": False,
                "preservation_evidence_refs": [],
            }
        ],
        "claims": [
            {
                "schema": "centinal26-claim-v1",
                "claim_id": "claim-1",
                "status": "VERIFIED",
                "proposition": "echo matched",
                "evidence_refs": ["ev-1"],
                "uncertainty": None,
            }
        ],
        "promotions": [
            {
                "schema": "centinal26-promotion-v1",
                "promotion_id": "p-1",
                "operation_id": "op-1",
                "executor": "agent",
                "verifier": "auditor",
                "authorized": True,
                "safe": True,
                "traceable": True,
                "verified": True,
                "evidence_refs": ["ev-1"],
            }
        ],
        "terminal_events": [
            {
                "schema": "centinal26-terminal-event-v1",
                "terminal_event_id": "terminal-1",
                "operation_id": "op-1",
                "status": "PASS",
                "evidence_refs": ["ev-1"],
            }
        ],
    }


def codes(bundle: object, *, now: datetime = NOW) -> set[str]:
    return {violation.code for violation in validate_bundle(bundle, now=now)}


def test_valid_bundle_passes() -> None:
    assert validate_bundle(valid_bundle(), now=NOW) == []


def test_runtime_contract_matches_declared_item_schemas() -> None:
    schema_root = Path(__file__).resolve().parents[1] / "schemas"
    contracts = {
        "authorization.schema.json": AUTH_FIELDS,
        "claim.schema.json": CLAIM_FIELDS,
        "governance_evidence.schema.json": EVIDENCE_FIELDS,
        "operation.schema.json": OPERATION_FIELDS,
        "promotion.schema.json": PROMOTION_FIELDS,
        "terminal_event.schema.json": TERMINAL_FIELDS,
    }
    for filename, fields in contracts.items():
        schema = json.loads((schema_root / filename).read_text(encoding="utf-8"))
        assert set(schema["required"]) == fields
        assert set(schema["properties"]) == fields
    bundle_schema = json.loads(
        (schema_root / "governance_bundle.schema.json").read_text(encoding="utf-8")
    )
    assert set(bundle_schema["required"]) == BUNDLE_FIELDS
    assert set(bundle_schema["properties"]) == BUNDLE_FIELDS


def test_empty_bundle_fails_closed() -> None:
    assert "BUNDLE_FIELD_REQUIRED" in codes({})


def test_declared_object_schema_is_enforced() -> None:
    bundle = valid_bundle()
    del bundle["claims"][0]["schema"]
    assert "FIELD_REQUIRED" in codes(bundle)


def test_self_authorization_fails_closed() -> None:
    bundle = valid_bundle()
    bundle["authorizations"][0]["issuer"] = "agent"
    assert "SELF_AUTHORIZATION_FORBIDDEN" in codes(bundle)


def test_authorization_scope_must_match_operation() -> None:
    bundle = valid_bundle()
    bundle["operations"][0]["scope"] = {"resource": "other"}
    assert "AUTH_SCOPE_MISMATCH" in codes(bundle)


def test_operation_risk_class_is_closed() -> None:
    bundle = valid_bundle()
    bundle["operations"][0]["risk_class"] = "ROOT"
    assert "OPERATION_RISK_INVALID" in codes(bundle)


def test_authorization_cannot_be_used_before_issue_time() -> None:
    bundle = valid_bundle()
    bundle["authorizations"][0]["issued_at"] = "2026-08-21T12:30:00+00:00"
    bundle["authorizations"][0]["expires_at"] = "2026-08-21T13:30:00+00:00"
    assert "AUTH_NOT_YET_VALID" in codes(bundle)


def test_derived_claim_requires_source_provenance() -> None:
    bundle = valid_bundle()
    bundle["claims"][0]["evidence_refs"] = []
    assert "CLAIM_PROVENANCE_REQUIRED" in codes(bundle)


def test_summary_cannot_replace_source() -> None:
    bundle = valid_bundle()
    bundle["evidence"][0]["source_type"] = "SUMMARY"
    assert "SUMMARY_CANNOT_REPLACE_SOURCE" in codes(bundle)


def test_future_evidence_cannot_satisfy_preservation_gate() -> None:
    bundle = valid_bundle()
    bundle["operations"][0]["destructive"] = True
    bundle["operations"][0]["preservation_evidence_refs"] = ["ev-1"]
    bundle["evidence"][0]["created_at"] = "2099-01-01T00:00:00+00:00"
    assert "EVIDENCE_FROM_FUTURE" in codes(bundle)


def test_destructive_action_requires_preservation() -> None:
    bundle = valid_bundle()
    bundle["operations"][0]["destructive"] = True
    assert "PRESERVATION_REQUIRED_BEFORE_DESTRUCTIVE_ACTION" in codes(bundle)


def test_promotion_requires_distinct_verifier_identity() -> None:
    bundle = valid_bundle()
    bundle["promotions"][0]["verifier"] = "agent"
    assert "INDEPENDENT_VERIFICATION_REQUIRED" in codes(bundle)


def test_terminal_state_is_closed_set() -> None:
    bundle = valid_bundle()
    bundle["terminal_events"][0]["status"] = "SUCCESS"
    assert "TERMINAL_STATE_INVALID" in codes(bundle)


def test_replay_time_controls_expiry_deterministically() -> None:
    bundle = valid_bundle()
    later = datetime(2026, 8, 21, 14, 0, tzinfo=UTC)
    assert "AUTH_EXPIRED" in codes(bundle, now=later)


def test_naive_replay_time_fails_closed() -> None:
    naive = datetime(2026, 8, 21, 12, 0, tzinfo=None)
    assert "REPLAY_TIME_INVALID" in codes(valid_bundle(), now=naive)


def test_malformed_reference_returns_violation_instead_of_raising() -> None:
    bundle = valid_bundle()
    bundle["operations"][0]["authorization_id"] = {}
    assert "OPERATION_AUTHORIZATION_ID_INVALID" in codes(bundle)


def test_malformed_json_values_never_raise() -> None:
    mutants = [None, {}, [], True, 7, ""]
    collection_names = (
        "authorizations",
        "evidence",
        "operations",
        "claims",
        "promotions",
        "terminal_events",
    )
    for collection in collection_names:
        fields = tuple(valid_bundle()[collection][0])
        for field in fields:
            for mutant in mutants:
                bundle = valid_bundle()
                bundle[collection][0][field] = mutant
                validate_bundle(bundle, now=NOW)
        for mutant in mutants:
            bundle = valid_bundle()
            bundle[collection] = mutant
            validate_bundle(bundle, now=NOW)


def test_duplicate_identifiers_are_rejected() -> None:
    bundle = valid_bundle()
    bundle["authorizations"].append(dict(bundle["authorizations"][0]))
    assert "DUPLICATE_AUTHORIZATION_ID" in codes(bundle)


def test_missing_claim_fields_do_not_pass_as_reported() -> None:
    bundle = valid_bundle()
    bundle["claims"] = [
        {
            "schema": "centinal26-claim-v1",
            "status": "REPORTED",
            "uncertainty": None,
        }
    ]
    assert "FIELD_REQUIRED" in codes(bundle)


def test_invalid_json_returns_structured_report(tmp_path) -> None:
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text("{", encoding="utf-8")
    report = validate_file(bundle_path, now=NOW)
    assert report["valid"] is False
    assert report["violations"][0]["code"] == "JSON_INVALID"
    json.dumps(report)
