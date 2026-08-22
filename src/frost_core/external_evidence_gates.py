from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class GateType(str, Enum):
    PROVIDER_HELD_RECORDS = "PROVIDER_HELD_RECORDS"
    ORIGINAL_EVIDENCE_BYTES = "ORIGINAL_EVIDENCE_BYTES"
    OWNER_AUTHORIZATION_FACT = "OWNER_AUTHORIZATION_FACT"
    PHYSICAL_ANDROID_EXECUTION = "PHYSICAL_ANDROID_EXECUTION"
    OAUTH_EXTERNAL_CONSENT = "OAUTH_EXTERNAL_CONSENT"


class GateStatus(str, Enum):
    SATISFIED = "SATISFIED"
    PENDING_EXTERNAL = "PENDING_EXTERNAL"
    BLOCKED_CONSENT = "BLOCKED_CONSENT"
    NOT_OBSERVED = "NOT_OBSERVED"
    REJECTED_SUBSTITUTE = "REJECTED_SUBSTITUTE"


@dataclass(frozen=True)
class EvidenceCandidate:
    source_class: str
    origin: str
    authentic: bool = False
    owner_attested: bool = False
    consent_granted: bool = False
    device_origin: bool = False
    original_bytes: bool = False


@dataclass(frozen=True)
class GateDecision:
    gate_type: GateType
    status: GateStatus
    reason: str


def evaluate_gate(
    gate_type: GateType, candidates: Iterable[EvidenceCandidate]
) -> GateDecision:
    items = tuple(candidates)

    if gate_type is GateType.PROVIDER_HELD_RECORDS:
        if any(i.authentic and i.source_class == "provider_record" for i in items):
            return GateDecision(
                gate_type,
                GateStatus.SATISFIED,
                "provider-originated record observed",
            )
        if items:
            return GateDecision(
                gate_type,
                GateStatus.REJECTED_SUBSTITUTE,
                "non-provider evidence cannot satisfy provider-held-record gate",
            )
        return GateDecision(
            gate_type,
            GateStatus.PENDING_EXTERNAL,
            "provider-originated records not currently available",
        )

    if gate_type is GateType.ORIGINAL_EVIDENCE_BYTES:
        if any(i.authentic and i.original_bytes for i in items):
            return GateDecision(
                gate_type,
                GateStatus.SATISFIED,
                "original bytes observed",
            )
        if items:
            return GateDecision(
                gate_type,
                GateStatus.REJECTED_SUBSTITUTE,
                "summary/reconstruction/hash-only evidence cannot substitute for original bytes",
            )
        return GateDecision(
            gate_type,
            GateStatus.PENDING_EXTERNAL,
            "original bytes not currently accessible",
        )

    if gate_type is GateType.OWNER_AUTHORIZATION_FACT:
        if any(i.owner_attested for i in items):
            return GateDecision(
                gate_type,
                GateStatus.SATISFIED,
                "owner authorization attestation observed",
            )
        if items:
            return GateDecision(
                gate_type,
                GateStatus.REJECTED_SUBSTITUTE,
                "behavioral or technical inference cannot establish owner authorization",
            )
        return GateDecision(
            gate_type,
            GateStatus.PENDING_EXTERNAL,
            "owner authorization fact not established",
        )

    if gate_type is GateType.PHYSICAL_ANDROID_EXECUTION:
        if any(i.authentic and i.device_origin for i in items):
            return GateDecision(
                gate_type,
                GateStatus.SATISFIED,
                "authentic Android/device-origin evidence observed",
            )
        if items:
            return GateDecision(
                gate_type,
                GateStatus.REJECTED_SUBSTITUTE,
                "host/cloud/simulation evidence cannot substitute for physical Android execution",
            )
        return GateDecision(
            gate_type,
            GateStatus.NOT_OBSERVED,
            "no authentic Android/device-origin evidence observed",
        )

    if gate_type is GateType.OAUTH_EXTERNAL_CONSENT:
        if any(i.consent_granted for i in items):
            return GateDecision(
                gate_type,
                GateStatus.SATISFIED,
                "OAuth consent observed",
            )
        if items:
            return GateDecision(
                gate_type,
                GateStatus.REJECTED_SUBSTITUTE,
                "credentials or assumed scope cannot substitute for explicit OAuth consent",
            )
        return GateDecision(
            gate_type,
            GateStatus.BLOCKED_CONSENT,
            "OAuth consent not granted",
        )

    raise ValueError(f"unsupported gate type: {gate_type}")
