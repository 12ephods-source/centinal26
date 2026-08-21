from __future__ import annotations

from datetime import UTC, datetime

from centinal26.governance import validate_bundle

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


def valid_bundle() -> dict:
    return {
        "authorizations": [{
            "authorization_id": "auth-1", "issuer": "human", "subject": "agent",
            "capability": "system.echo", "scope": {}, "risk_class": "HIGH",
            "issued_at": "2026-08-21T11:00:00+00:00", "expires_at": "2026-08-21T13:00:00+00:00",
            "signature": "sig"
        }],
        "evidence": [{
            "evidence_id": "ev-1", "sha256": DIGEST, "source_type": "SOURCE",
            "created_at": "2026-08-21T11:30:00+00:00", "immutable": True
        }],
        "operations": [{
            "operation_id": "op-1", "actor": "agent", "authorization_id": "auth-1",
            "capability_id": "system.echo", "scope": {}, "risk_class": "HIGH",
            "preconditions": [], "postconditions": ["output verified"], "destructive": False,
            "preservation_evidence_refs": []
        }],
        "claims": [{
            "claim_id": "claim-1", "status": "VERIFIED", "proposition": "echo matched",
            "evidence_refs": ["ev-1"], "uncertainty": None
        }],
        "promotions": [{
            "promotion_id": "p-1", "authorized": True, "safe": True, "traceable": True,
            "verified": True, "independent_verifier": True, "evidence_refs": ["ev-1"]
        }],
        "terminal_events": [{"status": "PASS"}],
    }


def codes(bundle: dict) -> set[str]:
    return {v.code for v in validate_bundle(bundle, now=NOW)}


def test_valid_bundle_passes() -> None:
    assert validate_bundle(valid_bundle(), now=NOW) == []


def test_self_authorization_fails_closed() -> None:
    bundle = valid_bundle()
    bundle["authorizations"][0]["issuer"] = "agent"
    assert "SELF_AUTHORIZATION_FORBIDDEN" in codes(bundle)


def test_derived_claim_requires_source_provenance() -> None:
    bundle = valid_bundle()
    bundle["claims"][0]["evidence_refs"] = []
    assert "CLAIM_PROVENANCE_REQUIRED" in codes(bundle)


def test_summary_cannot_replace_source() -> None:
    bundle = valid_bundle()
    bundle["evidence"][0]["source_type"] = "SUMMARY"
    assert "SUMMARY_CANNOT_REPLACE_SOURCE" in codes(bundle)


def test_destructive_action_requires_preservation() -> None:
    bundle = valid_bundle()
    bundle["operations"][0]["destructive"] = True
    assert "PRESERVATION_REQUIRED_BEFORE_DESTRUCTIVE_ACTION" in codes(bundle)


def test_promotion_requires_independent_verification() -> None:
    bundle = valid_bundle()
    bundle["promotions"][0]["independent_verifier"] = False
    assert "INDEPENDENT_VERIFICATION_REQUIRED" in codes(bundle)


def test_terminal_state_is_closed_set() -> None:
    bundle = valid_bundle()
    bundle["terminal_events"][0]["status"] = "SUCCESS"
    assert "TERMINAL_STATE_INVALID" in codes(bundle)


def test_replay_time_controls_expiry_deterministically() -> None:
    bundle = valid_bundle()
    later = datetime(2026, 8, 21, 14, 0, tzinfo=UTC)
    assert "AUTH_EXPIRED" in {v.code for v in validate_bundle(bundle, now=later)}
