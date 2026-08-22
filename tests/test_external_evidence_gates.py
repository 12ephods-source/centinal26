from frost_core.external_evidence_gates import (
    EvidenceCandidate,
    GateStatus,
    GateType,
    evaluate_gate,
)


def test_provider_record_gate_rejects_local_substitute():
    decision = evaluate_gate(
        GateType.PROVIDER_HELD_RECORDS,
        [EvidenceCandidate(source_class="local_log", origin="host", authentic=True)],
    )
    assert decision.status is GateStatus.REJECTED_SUBSTITUTE


def test_original_bytes_gate_rejects_hash_only_substitute():
    decision = evaluate_gate(
        GateType.ORIGINAL_EVIDENCE_BYTES,
        [EvidenceCandidate(source_class="hash", origin="derived", authentic=True)],
    )
    assert decision.status is GateStatus.REJECTED_SUBSTITUTE


def test_owner_authorization_requires_attestation():
    inferred = evaluate_gate(
        GateType.OWNER_AUTHORIZATION_FACT,
        [EvidenceCandidate(source_class="behavioral_inference", origin="analysis")],
    )
    assert inferred.status is GateStatus.REJECTED_SUBSTITUTE

    attested = evaluate_gate(
        GateType.OWNER_AUTHORIZATION_FACT,
        [EvidenceCandidate(source_class="owner_attestation", origin="owner", owner_attested=True)],
    )
    assert attested.status is GateStatus.SATISFIED


def test_physical_android_gate_rejects_host_execution():
    host = evaluate_gate(
        GateType.PHYSICAL_ANDROID_EXECUTION,
        [EvidenceCandidate(source_class="execution", origin="github-actions", authentic=True)],
    )
    assert host.status is GateStatus.REJECTED_SUBSTITUTE

    device = evaluate_gate(
        GateType.PHYSICAL_ANDROID_EXECUTION,
        [EvidenceCandidate(source_class="execution", origin="android/termux", authentic=True, device_origin=True)],
    )
    assert device.status is GateStatus.SATISFIED


def test_oauth_gate_requires_explicit_consent():
    blocked = evaluate_gate(GateType.OAUTH_EXTERNAL_CONSENT, [])
    assert blocked.status is GateStatus.BLOCKED_CONSENT

    granted = evaluate_gate(
        GateType.OAUTH_EXTERNAL_CONSENT,
        [EvidenceCandidate(source_class="oauth_grant", origin="provider", consent_granted=True)],
    )
    assert granted.status is GateStatus.SATISFIED
