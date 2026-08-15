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


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def mirror_record_hash(record: Mapping[str, Any]) -> str:
    """Return the canonical SHA-256 identity of an entire mirror record."""

    normalized = json.loads(_canonical_json(dict(record)))
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
    """Build the mirror-evidence fragment committed to the canonical ledger."""

    if mirror_kind not in MIRROR_KINDS:
        raise ValueError(f"unsupported mirror kind: {mirror_kind}")
    if not mirror_id:
        raise ValueError("mirror_id is required")
    if not authority_scope:
        raise ValueError("authority_scope is required")
    return {
        "mirror_kind": mirror_kind,
        "mirror_id": mirror_id,
        "mirror_sha256": mirror_record_hash(mirror_record),
        "authority_scope": authority_scope,
    }


def canonical_authority_grant(
    *, mirror_kind: str, mirror_id: str, authority_scope: str
) -> dict[str, str]:
    """Build the explicit affirmative authority grant required for mirror use."""

    if mirror_kind not in MIRROR_KINDS:
        raise ValueError(f"unsupported mirror kind: {mirror_kind}")
    if not mirror_id:
        raise ValueError("mirror_id is required")
    if not authority_scope:
        raise ValueError("authority_scope is required")
    return {
        "schema": AUTHORITY_GRANT_SCHEMA,
        "outcome": "ALLOW",
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
    A matching mirror binding is necessary but not sufficient: the canonical event
    must also carry an explicit affirmative, versioned authority grant.
    """

    if mirror_kind not in MIRROR_KINDS:
        return MirrorEvidenceVerification(False, "UNSUPPORTED_MIRROR_KIND")
    if not canonical_event_id or not canonical_event_hash or not required_scope:
        return MirrorEvidenceVerification(False, "MISSING_CANONICAL_BINDING")
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
    for field, value in expected_grant.items():
        actual = grant.get(field)
        if not isinstance(actual, str) or not hmac.compare_digest(actual, value):
            return MirrorEvidenceVerification(False, f"AUTHORITY_GRANT_MISMATCH:{field}")

    binding = event.payload.get("mirror_binding")
    if not isinstance(binding, dict):
        return MirrorEvidenceVerification(False, "MISSING_MIRROR_BINDING")

    expected_binding = canonical_mirror_binding(
        mirror_kind=mirror_kind,
        mirror_id=mirror_id,
        mirror_record=mirror_record,
        authority_scope=required_scope,
    )
    for field, value in expected_binding.items():
        actual = binding.get(field)
        if not isinstance(actual, str) or not hmac.compare_digest(actual, value):
            return MirrorEvidenceVerification(False, f"MIRROR_BINDING_MISMATCH:{field}")

    return MirrorEvidenceVerification(True, "CANONICAL_AUTHORITY_VERIFIED", event.event_hash)
