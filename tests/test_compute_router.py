from frost_core.compute_router import (
    ComputeProvider,
    ProviderStatus,
    Workload,
    route_workload,
)


def provider(
    provider_id: str,
    *,
    status: ProviderStatus = ProviderStatus.CONNECTED,
    capabilities: frozenset[str] = frozenset({"analysis"}),
    allowed: frozenset[str] = frozenset({"analysis"}),
    cost: float = 0.0,
    latency: float = 0.0,
    privacy_penalty: float = 0.0,
    verification_value: float = 0.0,
) -> ComputeProvider:
    return ComputeProvider(
        provider_id=provider_id,
        provider_class="CI_RUNNER",
        status=status,
        capabilities=capabilities,
        allowed_workloads=allowed,
        prohibited_uses=frozenset(),
        cost=cost,
        latency=latency,
        privacy_penalty=privacy_penalty,
        verification_value=verification_value,
    )


def test_external_gate_blocks_compute_substitution() -> None:
    workload = Workload(
        workload_type="analysis",
        required_capabilities=frozenset({"analysis"}),
        requires_physical_android=True,
    )
    decision = route_workload(workload, [provider("ci")])
    assert decision.eligible is False
    assert decision.provider_id is None
    assert "PHYSICAL_ANDROID_EXECUTION" in decision.reason


def test_satisfied_external_gate_allows_normal_routing() -> None:
    workload = Workload(
        workload_type="analysis",
        required_capabilities=frozenset({"analysis"}),
        requires_physical_android=True,
    )
    decision = route_workload(
        workload,
        [provider("ci", verification_value=1.0)],
        satisfied_external_gates=frozenset({"PHYSICAL_ANDROID_EXECUTION"}),
    )
    assert decision.eligible is True
    assert decision.provider_id == "ci"


def test_disconnected_or_consent_blocked_provider_is_never_selected() -> None:
    workload = Workload(
        workload_type="analysis",
        required_capabilities=frozenset({"analysis"}),
    )
    decision = route_workload(
        workload,
        [provider("hf", status=ProviderStatus.BLOCKED_CONSENT)],
    )
    assert decision.eligible is False
    assert decision.provider_id is None


def test_router_chooses_best_eligible_provider_by_bounded_score() -> None:
    workload = Workload(
        workload_type="analysis",
        required_capabilities=frozenset({"analysis"}),
    )
    slow = provider("slow", cost=1.0, latency=2.0, verification_value=1.0)
    strong = provider("strong", cost=0.1, latency=0.2, verification_value=1.0)
    decision = route_workload(workload, [slow, strong])
    assert decision.eligible is True
    assert decision.provider_id == "strong"


def test_missing_capability_fails_closed() -> None:
    workload = Workload(
        workload_type="analysis",
        required_capabilities=frozenset({"gpu"}),
    )
    decision = route_workload(workload, [provider("cpu")])
    assert decision.eligible is False
    assert decision.provider_id is None
