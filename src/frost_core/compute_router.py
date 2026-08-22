from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class ProviderStatus(str, Enum):
    CONNECTED = "CONNECTED"
    AVAILABLE_NOT_CONNECTED = "AVAILABLE_NOT_CONNECTED"
    BLOCKED_CONSENT = "BLOCKED_CONSENT"
    REQUIRES_CONFIG = "REQUIRES_CONFIG"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class ComputeProvider:
    provider_id: str
    provider_class: str
    status: ProviderStatus
    capabilities: frozenset[str]
    allowed_workloads: frozenset[str]
    prohibited_uses: frozenset[str]
    cost: float = 0.0
    latency: float = 0.0
    privacy_penalty: float = 0.0
    verification_value: float = 0.0


@dataclass(frozen=True)
class Workload:
    workload_type: str
    required_capabilities: frozenset[str]
    requires_physical_android: bool = False
    requires_provider_record: bool = False
    requires_original_bytes: bool = False
    requires_owner_authorization: bool = False
    requires_oauth_consent: bool = False


@dataclass(frozen=True)
class RoutingDecision:
    provider_id: str | None
    eligible: bool
    reason: str
    score: float | None = None


def _blocked_by_external_gate(workload: Workload) -> str | None:
    if workload.requires_physical_android:
        return "PHYSICAL_ANDROID_EXECUTION"
    if workload.requires_provider_record:
        return "PROVIDER_HELD_RECORDS"
    if workload.requires_original_bytes:
        return "ORIGINAL_EVIDENCE_BYTES"
    if workload.requires_owner_authorization:
        return "OWNER_AUTHORIZATION_FACT"
    if workload.requires_oauth_consent:
        return "OAUTH_EXTERNAL_CONSENT"
    return None


def route_workload(
    workload: Workload,
    providers: Iterable[ComputeProvider],
    *,
    satisfied_external_gates: frozenset[str] = frozenset(),
) -> RoutingDecision:
    blocked_gate = _blocked_by_external_gate(workload)
    if blocked_gate and blocked_gate not in satisfied_external_gates:
        return RoutingDecision(
            provider_id=None,
            eligible=False,
            reason=f"blocked by external gate {blocked_gate}",
        )

    eligible: list[tuple[float, ComputeProvider]] = []
    for provider in providers:
        if provider.status is not ProviderStatus.CONNECTED:
            continue
        if workload.workload_type not in provider.allowed_workloads:
            continue
        if not workload.required_capabilities.issubset(provider.capabilities):
            continue
        if "evidence_substitution" in provider.prohibited_uses and blocked_gate:
            continue
        score = (
            provider.verification_value * 3.0
            - provider.cost * 2.0
            - provider.latency
            - provider.privacy_penalty * 2.0
        )
        eligible.append((score, provider))

    if not eligible:
        return RoutingDecision(
            provider_id=None,
            eligible=False,
            reason="no connected provider satisfies workload contract",
        )

    score, provider = max(eligible, key=lambda item: (item[0], item[1].provider_id))
    return RoutingDecision(
        provider_id=provider.provider_id,
        eligible=True,
        reason="best eligible bounded provider",
        score=score,
    )
