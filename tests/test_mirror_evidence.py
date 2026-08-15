from centinal26.event_state import EventStore
from centinal26.mirror_evidence import (
    canonical_authority_grant,
    canonical_mirror_binding,
    verify_mirror_evidence,
)


def _bound_store(
    tmp_path,
    *,
    record,
    mirror_kind="AutomationVerificationVerdict",
    scope="merge",
    decision="allow",
):
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind=mirror_kind,
        mirror_id=record["id"],
        mirror_record=record,
        authority_scope=scope,
    )
    grant = canonical_authority_grant(
        mirror_kind=mirror_kind,
        mirror_id=record["id"],
        authority_scope=scope,
    )
    event = store.append(
        "DECISION_RECORDED",
        {"mirror_binding": binding, "authority_grant": grant, "decision": decision},
        entity_id="decision-1",
        event_id="event-1",
    )
    return store, event


def test_bound_mirror_record_is_accepted(tmp_path):
    record = {"id": "verdict-1", "verdict": "VERIFIED", "result_id": "result-1"}
    store, event = _bound_store(tmp_path, record=record)

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="merge",
    )

    assert result.ok is True
    assert result.reason == "CANONICAL_AUTHORITY_VERIFIED"


def test_denied_decision_fails_closed_even_with_matching_binding(tmp_path):
    record = {"id": "verdict-1", "verdict": "VERIFIED", "result_id": "result-1"}
    store, event = _bound_store(tmp_path, record=record, decision="deny")

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="merge",
    )

    assert result.ok is False
    assert result.reason == "AUTHORITY_DECISION_NOT_ALLOW"


def test_legacy_binding_without_explicit_grant_fails_closed(tmp_path):
    record = {"id": "verdict-1", "verdict": "VERIFIED", "result_id": "result-1"}
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        authority_scope="merge",
    )
    event = store.append(
        "DECISION_RECORDED",
        {"mirror_binding": binding, "decision": "allow"},
        entity_id="decision-1",
        event_id="event-1",
    )

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="merge",
    )

    assert result.ok is False
    assert result.reason == "MISSING_AUTHORITY_GRANT"


def test_authority_grant_scope_disagreement_fails_closed(tmp_path):
    record = {"id": "verdict-1", "verdict": "VERIFIED", "result_id": "result-1"}
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        authority_scope="merge",
    )
    wrong_grant = canonical_authority_grant(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        authority_scope="ga",
    )
    event = store.append(
        "DECISION_RECORDED",
        {"mirror_binding": binding, "authority_grant": wrong_grant, "decision": "allow"},
        entity_id="decision-1",
        event_id="event-1",
    )

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="merge",
    )

    assert result.ok is False
    assert result.reason == "AUTHORITY_GRANT_MISMATCH:authority_scope"


def test_verification_passed_event_is_not_implicitly_authoritative(tmp_path):
    record = {"id": "verdict-1", "verdict": "VERIFIED", "result_id": "result-1"}
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        authority_scope="merge",
    )
    grant = canonical_authority_grant(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        authority_scope="merge",
    )
    event = store.append(
        "VERIFICATION_PASSED",
        {"mirror_binding": binding, "authority_grant": grant},
        entity_id="verification-1",
        event_id="event-1",
    )

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="merge",
    )

    assert result.ok is False
    assert result.reason == "NON_AUTHORITY_EVENT"


def test_admin_edited_verdict_fails_closed(tmp_path):
    original = {"id": "verdict-1", "verdict": "VERIFICATION_FAILED", "result_id": "result-1"}
    store, event = _bound_store(tmp_path, record=original)
    edited = {**original, "verdict": "VERIFIED"}

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=edited,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="merge",
    )

    assert result.ok is False
    assert result.reason == "MIRROR_BINDING_MISMATCH:mirror_sha256"


def test_admin_edited_role_result_fails_closed(tmp_path):
    original = {"id": "result-1", "status": "FAILED_PRESERVED", "role": "BUILDER"}
    store, event = _bound_store(
        tmp_path,
        record=original,
        mirror_kind="AutomationRoleResult",
        scope="physical-promotion",
    )
    edited = {**original, "status": "EXECUTED_AWAITING_VERIFICATION"}

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationRoleResult",
        mirror_id="result-1",
        mirror_record=edited,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="physical-promotion",
    )

    assert result.ok is False
    assert result.reason == "MIRROR_BINDING_MISMATCH:mirror_sha256"


def test_missing_canonical_binding_fails_closed(tmp_path):
    record = {"id": "verdict-1", "verdict": "VERIFIED"}
    store = EventStore(tmp_path / "events.sqlite3")

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        canonical_event_id="",
        canonical_event_hash="",
        required_scope="ga",
    )

    assert result.ok is False
    assert result.reason == "MISSING_CANONICAL_BINDING"


def test_stale_or_different_canonical_hash_fails_closed(tmp_path):
    record = {"id": "verdict-1", "verdict": "VERIFIED"}
    store, event = _bound_store(tmp_path, record=record)

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash="f" * 64,
        required_scope="merge",
    )

    assert result.ok is False
    assert result.reason == "CANONICAL_EVENT_HASH_MISMATCH"


def test_scope_disagreement_fails_closed(tmp_path):
    record = {"id": "verdict-1", "verdict": "VERIFIED"}
    store, event = _bound_store(tmp_path, record=record, scope="merge")

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="ga",
    )

    assert result.ok is False
    assert result.reason == "AUTHORITY_GRANT_MISMATCH:authority_scope"


def test_non_authority_event_cannot_authorize_mirror(tmp_path):
    record = {"id": "result-1", "status": "EXECUTED_AWAITING_VERIFICATION"}
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind="AutomationRoleResult",
        mirror_id="result-1",
        mirror_record=record,
        authority_scope="merge",
    )
    grant = canonical_authority_grant(
        mirror_kind="AutomationRoleResult",
        mirror_id="result-1",
        authority_scope="merge",
    )
    event = store.append(
        "ARTIFACT_CREATED",
        {"mirror_binding": binding, "authority_grant": grant},
        entity_id="artifact-1",
        event_id="event-1",
    )

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationRoleResult",
        mirror_id="result-1",
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="merge",
    )

    assert result.ok is False
    assert result.reason == "NON_AUTHORITY_EVENT"


def test_tampered_canonical_chain_fails_closed(tmp_path):
    record = {"id": "verdict-1", "verdict": "VERIFIED"}
    store, event = _bound_store(tmp_path, record=record)
    store.db.execute("DROP TRIGGER events_no_update")
    store.db.execute("UPDATE events SET payload_json='{}' WHERE event_id='event-1'")
    store.db.commit()

    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id="verdict-1",
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope="merge",
    )

    assert result.ok is False
    assert result.reason == "CANONICAL_CHAIN_INVALID"
