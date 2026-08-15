from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from centinal26.event_state import EventStore

MIRROR_KINDS = frozenset({"AutomationRoleResult", "AutomationVerificationVerdict"})
AUTHORITY_EVENT_TYPES = frozenset({"DECISION_RECORDED", "VERIFICATION_PASSED"})


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
    """Build the payload fragment that must be committed to the canonical ledger.

    Base44 mirror rows are mutable coordination records. This binding becomes
    authoritative only after it is included in an append-only Centinal26 event.
    """

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
    """Fail closed unless mutable mirror evidence matches canonical ledger truth.

    ``canonical_event_id`` and ``canonical_event_hash`` must come from a trusted
    canonical reference, never from fields read only from the mutable mirror row.
    Consequential consumers must provide the exact authority scope they require.
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
    if event.type not in AUTHORITY_EVENT_TYPES:
        return MirrorEvidenceVerification(False, "NON_AUTHORITY_EVENT")

    binding = event.payload.get("mirror_binding")
    if not isinstance(binding, dict):
        return MirrorEvidenceVerification(False, "MISSING_MIRROR_BINDING")

    expected = canonical_mirror_binding(
        mirror_kind=mirror_kind,
        mirror_id=mirror_id,
        mirror_record=mirror_record,
        authority_scope=required_scope,
    )
    for field, value in expected.items():
        actual = binding.get(field)
        if not isinstance(actual, str) or not hmac.compare_digest(actual, value):
            return MirrorEvidenceVerification(False, f"MIRROR_BINDING_MISMATCH:{field}")

    return MirrorEvidenceVerification(True, "CANONICAL_BINDING_VERIFIED", event.event_hash)
