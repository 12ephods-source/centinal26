from frost_core.compute_router import ComputeProvider, ProviderStatus, Workload
from frost_core.external_evidence_gates import EvidenceCandidate, GateStatus, GateType
from frost_core.external_evidence_orchestrator import orchestrate


def connected_provider() -> ComputeProvider:
    return ComputeProvider(
        provider_id="ci",
        provider_class="CI_RUNNER",
        status=ProviderStatus.CONNECTED,
        capabilities=frozenset({"analysis"}),
        allowed_workloads=frozenset({"analysis"}),
        prohibited_uses=frozenset(),
        verification_value=1.0,
    )


def test_blocked_physical_gate_does_not_stall_unrelated_work() -> None:
    physical = Workload(
        workload_type="analysis",
        required_capabilities=frozenset({"analysis"}),
        requires_physical_android=True,
    )
    unrelated = Workload(
        workload_type="analysis",
        required_capabilities=frozenset({"analysis"}),
    )
    state = orchestrate({}, (physical, unrelated), (connected_provider(),))
    assert state.gates[GateType.PHYSICAL_ANDROID_EXECUTION] is GateStatus.NOT_OBSERVED
    assert state.work[0].routing.eligible is False
    assert state.work[1].routing.eligible is True
    assert state.work[1].routing.provider_id == "ci"


def test_real_device_evidence_unlocks_only_physical_gate() -> None:
    candidates = {
        GateType.PHYSICAL_ANDROID_EXECUTION: (
            EvidenceCandidate(
                source_class="execution",
                origin="android/termux",
                authentic=True,
                device_origin=True,
            ),
        )
    }
    physical = Workload(
        workload_type="analysis",
        required_capabilities=frozenset({"analysis"}),
        requires_physical_android=True,
    )
    state = orchestrate(candidates, (physical,), (connected_provider(),))
    assert state.gates[GateType.PHYSICAL_ANDROID_EXECUTION] is GateStatus.SATISFIED
    assert state.gates[GateType.OAUTH_EXTERNAL_CONSENT] is GateStatus.BLOCKED_CONSENT
    assert state.work[0].routing.eligible is True


def test_host_evidence_cannot_unlock_physical_work() -> None:
    candidates = {
        GateType.PHYSICAL_ANDROID_EXECUTION: (
            EvidenceCandidate(
                source_class="execution",
                origin="github-actions",
                authentic=True,
            ),
        )
    }
    physical = Workload(
        workload_type="analysis",
        required_capabilities=frozenset({"analysis"}),
        requires_physical_android=True,
    )
    state = orchestrate(candidates, (physical,), (connected_provider(),))
    assert state.gates[GateType.PHYSICAL_ANDROID_EXECUTION] is GateStatus.REJECTED_SUBSTITUTE
    assert state.work[0].routing.eligible is False
