import pytest

from centinal26.event_state import EventStore
from centinal26.mirror_evidence import (
    canonical_authority_grant,
    canonical_mirror_binding,
    verify_mirror_evidence,
)


def _verdict_record(**overrides):
    record = {
        "id": "base44-row-verdict-1",
        "verdict_id": "verdict-1",
        "result_id": "result-1",
        "contract_id": "contract-1",
        "verdict": "VERIFIED",
        "verifier": "Frost Judge",
        "details_json": '{"tests":["independent"]}',
        "evidence_hash": "b" * 64,
        "verdict_hash": "a" * 64,
        "created_at_client": "2026-08-15T17:00:00-06:00",
        "created_date": "2026-08-15T23:00:01.000000",
        "updated_date": "2026-08-15T23:00:01.000000",
        "created_by_id": "admin-1",
        "is_sample": False,
    }
    record.update(overrides)
    return record


def _role_result(**overrides):
    record = {
        "id": "base44-row-result-1",
        "result_id": "result-1",
        "contract_id": "contract-1",
        "role": "BUILDER",
        "status": "EXECUTED_AWAITING_VERIFICATION",
        "payload_json": '{"head":"abc"}',
        "evidence_hash": "d" * 64,
        "result_hash": "c" * 64,
        "created_at_client": "2026-08-15T16:00:00-06:00",
        "created_date": "2026-08-15T22:00:01.000000",
        "updated_date": "2026-08-15T22:00:01.000000",
        "created_by_id": "admin-1",
        "is_sample": False,
    }
    record.update(overrides)
    return record


def _logical_id(record, mirror_kind):
    if mirror_kind == "AutomationVerificationVerdict":
        return record["verdict_id"]
    return record["result_id"]


def _bound_store(
    tmp_path,
    *,
    record,
    mirror_kind="AutomationVerificationVerdict",
    scope="merge",
    decision="allow",
    binding_mutator=None,
    grant_mutator=None,
):
    mirror_id = _logical_id(record, mirror_kind)
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind=mirror_kind,
        mirror_id=mirror_id,
        mirror_record=record,
        authority_scope=scope,
    )
    grant = canonical_authority_grant(
        mirror_kind=mirror_kind,
        mirror_id=mirror_id,
        authority_scope=scope,
    )
    if binding_mutator is not None:
        binding_mutator(binding)
    if grant_mutator is not None:
        grant_mutator(grant)
    event = store.append(
        "DECISION_RECORDED",
        {"mirror_binding": binding, "authority_grant": grant, "decision": decision},
        entity_id="decision-1",
        event_id="event-1",
    )
    return store, event


def _verify(
    store,
    event,
    *,
    record,
    mirror_kind="AutomationVerificationVerdict",
    scope="merge",
    mirror_id=None,
):
    return verify_mirror_evidence(
        store,
        mirror_kind=mirror_kind,
        mirror_id=mirror_id or _logical_id(record, mirror_kind),
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash=event.event_hash,
        required_scope=scope,
    )


@pytest.mark.parametrize(
    ("mirror_kind", "record"),
    [
        ("AutomationVerificationVerdict", _verdict_record()),
        ("AutomationRoleResult", _role_result()),
    ],
)
def test_complete_bound_mirror_record_is_accepted(tmp_path, mirror_kind, record):
    store, event = _bound_store(tmp_path, record=record, mirror_kind=mirror_kind)
    result = _verify(store, event, record=record, mirror_kind=mirror_kind)
    assert result.ok is True
    assert result.reason == "CANONICAL_AUTHORITY_VERIFIED"


@pytest.mark.parametrize(
    "missing_field",
    [
        "verdict_id",
        "result_id",
        "contract_id",
        "verdict",
        "verifier",
        "details_json",
        "verdict_hash",
        "created_at_client",
    ],
)
def test_partial_verdict_projection_fails_closed(tmp_path, missing_field):
    original = _verdict_record()
    store, event = _bound_store(tmp_path, record=original)
    partial = dict(original)
    partial.pop(missing_field)
    result = _verify(store, event, record=partial, mirror_id="verdict-1")
    assert result.ok is False
    assert result.reason == f"MISSING_MIRROR_FIELD:{missing_field}"


@pytest.mark.parametrize(
    "missing_field",
    [
        "result_id",
        "contract_id",
        "role",
        "status",
        "payload_json",
        "result_hash",
        "created_at_client",
    ],
)
def test_partial_role_result_projection_fails_closed(tmp_path, missing_field):
    original = _role_result()
    store, event = _bound_store(
        tmp_path, record=original, mirror_kind="AutomationRoleResult"
    )
    partial = dict(original)
    partial.pop(missing_field)
    result = _verify(
        store,
        event,
        record=partial,
        mirror_kind="AutomationRoleResult",
        mirror_id="result-1",
    )
    assert result.ok is False
    assert result.reason == f"MISSING_MIRROR_FIELD:{missing_field}"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("result_id", "result-2"),
        ("contract_id", "contract-2"),
        ("verdict", "VERIFICATION_FAILED"),
        ("verifier", "Other Verifier"),
        ("details_json", '{"tests":["changed"]}'),
        ("evidence_hash", "e" * 64),
        ("verdict_hash", "f" * 64),
        ("created_at_client", "2026-08-15T17:01:00-06:00"),
    ],
)
def test_verdict_authority_field_mutation_fails_closed(tmp_path, field, replacement):
    original = _verdict_record()
    store, event = _bound_store(tmp_path, record=original)
    edited = {**original, field: replacement}
    result = _verify(store, event, record=edited, mirror_id="verdict-1")
    assert result.ok is False


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("result_id", "result-2"),
        ("contract_id", "contract-2"),
        ("role", "SRE"),
        ("status", "FAILED_PRESERVED"),
        ("payload_json", '{"head":"changed"}'),
        ("evidence_hash", "e" * 64),
        ("result_hash", "f" * 64),
        ("created_at_client", "2026-08-15T16:01:00-06:00"),
    ],
)
def test_role_result_authority_field_mutation_fails_closed(tmp_path, field, replacement):
    original = _role_result()
    store, event = _bound_store(
        tmp_path, record=original, mirror_kind="AutomationRoleResult"
    )
    edited = {**original, field: replacement}
    result = _verify(
        store,
        event,
        record=edited,
        mirror_kind="AutomationRoleResult",
        mirror_id="result-1",
    )
    assert result.ok is False


def test_logical_verdict_id_must_equal_mirror_id(tmp_path):
    record = _verdict_record()
    store, event = _bound_store(tmp_path, record=record)
    result = _verify(store, event, record=record, mirror_id="verdict-other")
    assert result.ok is False
    assert result.reason == "MIRROR_LOGICAL_ID_MISMATCH"


def test_logical_role_result_id_must_equal_mirror_id(tmp_path):
    record = _role_result()
    store, event = _bound_store(
        tmp_path, record=record, mirror_kind="AutomationRoleResult"
    )
    result = _verify(
        store,
        event,
        record=record,
        mirror_kind="AutomationRoleResult",
        mirror_id="result-other",
    )
    assert result.ok is False
    assert result.reason == "MIRROR_LOGICAL_ID_MISMATCH"


def test_unknown_authority_bearing_field_fails_closed(tmp_path):
    original = _verdict_record()
    store, event = _bound_store(tmp_path, record=original)
    edited = {**original, "approval_override": "ALLOW"}
    result = _verify(store, event, record=edited)
    assert result.ok is False
    assert result.reason == "UNKNOWN_MIRROR_FIELD:approval_override"


def test_wrong_field_type_fails_closed(tmp_path):
    original = _verdict_record()
    store, event = _bound_store(tmp_path, record=original)
    edited = {**original, "details_json": {"tests": ["changed"]}}
    result = _verify(store, event, record=edited)
    assert result.ok is False
    assert result.reason == "INVALID_MIRROR_FIELD:details_json"


def test_invalid_json_field_fails_closed(tmp_path):
    original = _role_result()
    store, event = _bound_store(
        tmp_path, record=original, mirror_kind="AutomationRoleResult"
    )
    edited = {**original, "payload_json": "{not-json"}
    result = _verify(store, event, record=edited, mirror_kind="AutomationRoleResult")
    assert result.ok is False
    assert result.reason == "INVALID_MIRROR_JSON:payload_json"


def test_unknown_mirror_schema_version_in_binding_fails_closed(tmp_path):
    record = _verdict_record()

    def mutate(binding):
        binding["schema"] = "centinal26-base44-automation-verification-verdict-v999"

    store, event = _bound_store(tmp_path, record=record, binding_mutator=mutate)
    result = _verify(store, event, record=record)
    assert result.ok is False
    assert result.reason == "MIRROR_BINDING_MISMATCH:schema"


def test_extra_authority_grant_field_fails_closed(tmp_path):
    record = _verdict_record()

    def mutate(grant):
        grant["override"] = "ALLOW"

    store, event = _bound_store(tmp_path, record=record, grant_mutator=mutate)
    result = _verify(store, event, record=record)
    assert result.ok is False
    assert result.reason == "AUTHORITY_GRANT_SCHEMA_MISMATCH"


def test_denied_decision_fails_closed_even_with_matching_binding(tmp_path):
    record = _verdict_record()
    store, event = _bound_store(tmp_path, record=record, decision="deny")
    result = _verify(store, event, record=record)
    assert result.ok is False
    assert result.reason == "AUTHORITY_DECISION_NOT_ALLOW"


def test_legacy_binding_without_explicit_grant_fails_closed(tmp_path):
    record = _verdict_record()
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id=record["verdict_id"],
        mirror_record=record,
        authority_scope="merge",
    )
    event = store.append(
        "DECISION_RECORDED",
        {"mirror_binding": binding, "decision": "allow"},
        entity_id="decision-1",
        event_id="event-1",
    )
    result = _verify(store, event, record=record)
    assert result.ok is False
    assert result.reason == "MISSING_AUTHORITY_GRANT"


def test_authority_grant_scope_disagreement_fails_closed(tmp_path):
    record = _verdict_record()
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id=record["verdict_id"],
        mirror_record=record,
        authority_scope="merge",
    )
    wrong_grant = canonical_authority_grant(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id=record["verdict_id"],
        authority_scope="ga",
    )
    event = store.append(
        "DECISION_RECORDED",
        {"mirror_binding": binding, "authority_grant": wrong_grant, "decision": "allow"},
        entity_id="decision-1",
        event_id="event-1",
    )
    result = _verify(store, event, record=record)
    assert result.ok is False
    assert result.reason == "AUTHORITY_GRANT_MISMATCH:authority_scope"


def test_verification_passed_event_is_not_implicitly_authoritative(tmp_path):
    record = _verdict_record()
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id=record["verdict_id"],
        mirror_record=record,
        authority_scope="merge",
    )
    grant = canonical_authority_grant(
        mirror_kind="AutomationVerificationVerdict",
        mirror_id=record["verdict_id"],
        authority_scope="merge",
    )
    event = store.append(
        "VERIFICATION_PASSED",
        {"mirror_binding": binding, "authority_grant": grant},
        entity_id="verification-1",
        event_id="event-1",
    )
    result = _verify(store, event, record=record)
    assert result.ok is False
    assert result.reason == "NON_AUTHORITY_EVENT"


def test_valid_chain_bound_to_wrong_result_fails_closed(tmp_path):
    current = _verdict_record(result_id="result-1")
    other = _verdict_record(result_id="result-2")
    store, event = _bound_store(tmp_path, record=other)
    result = _verify(store, event, record=current)
    assert result.ok is False
    assert result.reason in {
        "MIRROR_BINDING_MISMATCH:result_id",
        "MIRROR_BINDING_MISMATCH:mirror_sha256",
    }


def test_missing_canonical_binding_fails_closed(tmp_path):
    record = _verdict_record()
    store = EventStore(tmp_path / "events.sqlite3")
    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id=record["verdict_id"],
        mirror_record=record,
        canonical_event_id="",
        canonical_event_hash="",
        required_scope="ga",
    )
    assert result.ok is False
    assert result.reason == "MISSING_CANONICAL_BINDING"


def test_stale_or_different_canonical_hash_fails_closed(tmp_path):
    record = _verdict_record()
    store, event = _bound_store(tmp_path, record=record)
    result = verify_mirror_evidence(
        store,
        mirror_kind="AutomationVerificationVerdict",
        mirror_id=record["verdict_id"],
        mirror_record=record,
        canonical_event_id=event.event_id,
        canonical_event_hash="f" * 64,
        required_scope="merge",
    )
    assert result.ok is False
    assert result.reason == "CANONICAL_EVENT_HASH_MISMATCH"


def test_scope_disagreement_fails_closed(tmp_path):
    record = _verdict_record()
    store, event = _bound_store(tmp_path, record=record, scope="merge")
    result = _verify(store, event, record=record, scope="ga")
    assert result.ok is False
    assert result.reason == "AUTHORITY_GRANT_MISMATCH:authority_scope"


def test_non_authority_event_cannot_authorize_mirror(tmp_path):
    record = _role_result()
    store = EventStore(tmp_path / "events.sqlite3")
    binding = canonical_mirror_binding(
        mirror_kind="AutomationRoleResult",
        mirror_id=record["result_id"],
        mirror_record=record,
        authority_scope="merge",
    )
    grant = canonical_authority_grant(
        mirror_kind="AutomationRoleResult",
        mirror_id=record["result_id"],
        authority_scope="merge",
    )
    event = store.append(
        "ARTIFACT_CREATED",
        {"mirror_binding": binding, "authority_grant": grant},
        entity_id="artifact-1",
        event_id="event-1",
    )
    result = _verify(store, event, record=record, mirror_kind="AutomationRoleResult")
    assert result.ok is False
    assert result.reason == "NON_AUTHORITY_EVENT"


def test_tampered_canonical_chain_fails_closed(tmp_path):
    record = _verdict_record()
    store, event = _bound_store(tmp_path, record=record)
    store.db.execute("DROP TRIGGER events_no_update")
    store.db.execute("UPDATE events SET payload_json='{}' WHERE event_id='event-1'")
    store.db.commit()
    result = _verify(store, event, record=record)
    assert result.ok is False
    assert result.reason == "CANONICAL_CHAIN_INVALID"
