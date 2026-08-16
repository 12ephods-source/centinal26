from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from centinal26.event_state import EventStore

MIRROR_KINDS = frozenset({"AutomationRoleResult", "AutomationVerificationVerdict"})
AUTHORITY_EVENT_TYPE = "DECISION_RECORDED"
AUTHORITY_GRANT_SCHEMA = "centinal26-mirror-authority-grant-v1"

_MIRROR_SCHEMA_VERSION = {
    "AutomationRoleResult": "centinal26-base44-automation-role-result-v1",
    "AutomationVerificationVerdict": "centinal26-base44-automation-verification-verdict-v1",
}
_MIRROR_REQUIRED_FIELDS = {
    "AutomationRoleResult": (
        "result_id",
        "contract_id",
        "role",
        "status",
        "payload_json",
        "result_hash",
        "created_at_client",
    ),
    "AutomationVerificationVerdict": (
        "verdict_id",
        "result_id",
        "contract_id",
        "verdict",
        "verifier",
        "details_json",
        "verdict_hash",
        "created_at_client",
    ),
}
_MIRROR_OPTIONAL_AUTHORITY_FIELDS = {
    "AutomationRoleResult": ("evidence_hash",),
    "AutomationVerificationVerdict": ("evidence_hash",),
}
_BASE44_SYSTEM_FIELDS = frozenset(
    {"id", "created_date", "updated_date", "created_by_id", "is_sample"}
)
_ALLOWED_ROLES = frozenset({"GOVERNOR", "BUILDER", "JUDGE", "SRE", "EVOLUTION"})
_ALLOWED_VERDICTS = frozenset(
    {"VERIFIED", "VERIFICATION_FAILED", "INCONCLUSIVE", "BLOCKED_EXTERNAL"}
)
_HEX = frozenset("0123456789abcdef")


class MirrorSchemaError(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in _HEX for char in value.lower())


def _require_nonempty_string(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise MirrorSchemaError(f"INVALID_MIRROR_FIELD:{field}")
    return value


def _require_json_string(record: Mapping[str, Any], field: str) -> str:
    value = _require_nonempty_string(record, field)
    try:
        json.loads(value, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (TypeError, ValueError, json.JSONDecodeError):
        raise MirrorSchemaError(f"INVALID_MIRROR_JSON:{field}") from None
    return value


def _schema_for_kind(mirror_kind: str) -> str:
    try:
        return _MIRROR_SCHEMA_VERSION[mirror_kind]
    except KeyError:
        raise MirrorSchemaError("UNSUPPORTED_MIRROR_KIND") from None


def canonical_mirror_projection(
    *, mirror_kind: str, mirror_id: str, mirror_record: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate a full Base44 mirror row and build its canonical authority projection.

    The caller may supply Base44's non-authority system metadata, but it may not select
    an arbitrary subset of authority fields or inject unknown authority-bearing fields.
    The projection is constructed here from the versioned entity-kind schema.
    """

    schema = _schema_for_kind(mirror_kind)
    if not isinstance(mirror_record, Mapping):
        raise MirrorSchemaError("INVALID_MIRROR_RECORD")
    if not isinstance(mirror_id, str) or not mirror_id:
        raise MirrorSchemaError("MISSING_MIRROR_ID")

    required_fields = _MIRROR_REQUIRED_FIELDS[mirror_kind]
    optional_fields = _MIRROR_OPTIONAL_AUTHORITY_FIELDS[mirror_kind]
    known_fields = set(required_fields) | set(optional_fields) | set(_BASE44_SYSTEM_FIELDS)
    unknown_fields = sorted(set(mirror_record) - known_fields)
    if unknown_fields:
        raise MirrorSchemaError(f"UNKNOWN_MIRROR_FIELD:{unknown_fields[0]}")

    missing_fields = [field for field in required_fields if field not in mirror_record]
    if missing_fields:
        raise MirrorSchemaError(f"MISSING_MIRROR_FIELD:{missing_fields[0]}")

    projection: dict[str, Any] = {
        "schema": schema,
        "mirror_kind": mirror_kind,
    }
    for field in required_fields:
        projection[field] = _require_nonempty_string(mirror_record, field)
    for field in optional_fields:
        value = mirror_record.get(field)
        if value is not None and not isinstance(value, str):
            raise MirrorSchemaError(f"INVALID_MIRROR_FIELD:{field}")
        projection[field] = value

    logical_id_field = (
        "verdict_id" if mirror_kind == "AutomationVerificationVerdict" else "result_id"
    )
    logical_id = projection[logical_id_field]
    if not hmac.compare_digest(logical_id, mirror_id):
        raise MirrorSchemaError("MIRROR_LOGICAL_ID_MISMATCH")

    if mirror_kind == "AutomationVerificationVerdict":
        if projection["verdict"] not in _ALLOWED_VERDICTS:
            raise MirrorSchemaError("INVALID_MIRROR_FIELD:verdict")
        if projection["verifier"] != "Frost Judge":
            raise MirrorSchemaError("INVALID_MIRROR_FIELD:verifier")
        _require_json_string(mirror_record, "details_json")
        if not _is_sha256(projection["verdict_hash"]):
            raise MirrorSchemaError("INVALID_MIRROR_FIELD:verdict_hash")
    else:
        if projection["role"] not in _ALLOWED_ROLES:
            raise MirrorSchemaError("INVALID_MIRROR_FIELD:role")
        _require_json_string(mirror_record, "payload_json")
        if not _is_sha256(projection["result_hash"]):
            raise MirrorSchemaError("INVALID_MIRROR_FIELD:result_hash")

    evidence_hash = projection.get("evidence_hash")
    if evidence_hash not in (None, "") and not _is_sha256(evidence_hash):
        raise MirrorSchemaError("INVALID_MIRROR_FIELD:evidence_hash")

    return projection


def mirror_record_hash(
    record: Mapping[str, Any],
    *,
    mirror_kind: str | None = None,
    mirror_id: str | None = None,
) -> str:
    """Return a canonical SHA-256 identity.

    Authority callers must provide ``mirror_kind`` and ``mirror_id`` so the verifier,
    rather than the caller, chooses and validates the complete projection.
    """

    if mirror_kind is None or mirror_id is None:
        normalized = json.loads(_canonical_json(dict(record)))
    else:
        normalized = canonical_mirror_projection(
            mirror_kind=mirror_kind,
            mirror_id=mirror_id,
            mirror_record=record,
        )
    return hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MirrorEvidenceVerification:
    ok: bool
    reason: str
    canonical_event_hash: str | None = None


def canonical_mirror_binding(
    *,
    mirror_kind: str,
    mirror_id: str,
    mirror_record: Mapping[str, Any],
    authority_scope: str,
) -> dict[str, str]:
    """Build the versioned mirror-evidence fragment committed to the canonical ledger."""

    if not authority_scope:
        raise ValueError("authority_scope is required")
    projection = canonical_mirror_projection(
        mirror_kind=mirror_kind,
        mirror_id=mirror_id,
        mirror_record=mirror_record,
    )
    return {
        "schema": projection["schema"],
        "mirror_kind": mirror_kind,
        "mirror_id": mirror_id,
        "contract_id": projection["contract_id"],
        "result_id": projection["result_id"],
        "mirror_sha256": hashlib.sha256(
            _canonical_json(projection).encode("utf-8")
        ).hexdigest(),
        "authority_scope": authority_scope,
    }


def canonical_authority_grant(
    *, mirror_kind: str, mirror_id: str, authority_scope: str
) -> dict[str, str]:
    """Build the explicit affirmative authority grant required for mirror use."""

    schema = _schema_for_kind(mirror_kind)
    if not mirror_id:
        raise ValueError("mirror_id is required")
    if not authority_scope:
        raise ValueError("authority_scope is required")
    return {
        "schema": AUTHORITY_GRANT_SCHEMA,
        "outcome": "ALLOW",
        "mirror_schema": schema,
        "mirror_kind": mirror_kind,
        "mirror_id": mirror_id,
        "authority_scope": authority_scope,
    }


def verify_mirror_evidence(
    store: EventStore,
    *,
    mirror_kind: str,
    mirror_id: str,
    mirror_record: Mapping[str, Any],
    canonical_event_id: str,
    canonical_event_hash: str,
    required_scope: str,
) -> MirrorEvidenceVerification:
    """Fail closed unless mutable mirror evidence has explicit canonical authority.

    ``canonical_event_id`` and ``canonical_event_hash`` must come from a trusted
    canonical reference, never from fields read only from the mutable mirror row.
    Consequential consumers must provide the exact authority scope they require.
    The verifier constructs and hashes the complete versioned authority projection;
    callers cannot choose an arbitrary subset of mirror fields.
    """

    if mirror_kind not in MIRROR_KINDS:
        return MirrorEvidenceVerification(False, "UNSUPPORTED_MIRROR_KIND")
    if not canonical_event_id or not canonical_event_hash or not required_scope:
        return MirrorEvidenceVerification(False, "MISSING_CANONICAL_BINDING")

    try:
        projection = canonical_mirror_projection(
            mirror_kind=mirror_kind,
            mirror_id=mirror_id,
            mirror_record=mirror_record,
        )
    except MirrorSchemaError as exc:
        return MirrorEvidenceVerification(False, exc.reason)

    if not store.verify_chain():
        return MirrorEvidenceVerification(False, "CANONICAL_CHAIN_INVALID")

    event = next(
        (candidate for candidate in store.events() if candidate.event_id == canonical_event_id),
        None,
    )
    if event is None:
        return MirrorEvidenceVerification(False, "CANONICAL_EVENT_NOT_FOUND")
    if not hmac.compare_digest(event.event_hash, canonical_event_hash):
        return MirrorEvidenceVerification(False, "CANONICAL_EVENT_HASH_MISMATCH")
    if event.type != AUTHORITY_EVENT_TYPE:
        return MirrorEvidenceVerification(False, "NON_AUTHORITY_EVENT")

    decision = event.payload.get("decision")
    if decision is not None and decision != "allow":
        return MirrorEvidenceVerification(False, "AUTHORITY_DECISION_NOT_ALLOW")

    grant = event.payload.get("authority_grant")
    if not isinstance(grant, dict):
        return MirrorEvidenceVerification(False, "MISSING_AUTHORITY_GRANT")
    expected_grant = canonical_authority_grant(
        mirror_kind=mirror_kind,
        mirror_id=mirror_id,
        authority_scope=required_scope,
    )
    if set(grant) != set(expected_grant):
        return MirrorEvidenceVerification(False, "AUTHORITY_GRANT_SCHEMA_MISMATCH")
    for field, value in expected_grant.items():
        actual = grant.get(field)
        if not isinstance(actual, str) or not hmac.compare_digest(actual, value):
            return MirrorEvidenceVerification(False, f"AUTHORITY_GRANT_MISMATCH:{field}")

    binding = event.payload.get("mirror_binding")
    if not isinstance(binding, dict):
        return MirrorEvidenceVerification(False, "MISSING_MIRROR_BINDING")

    expected_binding = {
        "schema": projection["schema"],
        "mirror_kind": mirror_kind,
        "mirror_id": mirror_id,
        "contract_id": projection["contract_id"],
        "result_id": projection["result_id"],
        "mirror_sha256": hashlib.sha256(
            _canonical_json(projection).encode("utf-8")
        ).hexdigest(),
        "authority_scope": required_scope,
    }
    if set(binding) != set(expected_binding):
        return MirrorEvidenceVerification(False, "MIRROR_BINDING_SCHEMA_MISMATCH")
    for field, value in expected_binding.items():
        actual = binding.get(field)
        if not isinstance(actual, str) or not hmac.compare_digest(actual, value):
            return MirrorEvidenceVerification(False, f"MIRROR_BINDING_MISMATCH:{field}")

    return MirrorEvidenceVerification(True, "CANONICAL_AUTHORITY_VERIFIED", event.event_hash)
