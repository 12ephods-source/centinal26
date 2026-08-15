from __future__ import annotations

import hashlib
import io
import sys
import threading
import zipfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from frost_core.capability_factory import (
    REQUIRED_PROMOTION_GATES,
    CapabilityCandidate,
    CapabilityFactoryLedger,
    CapabilityStage,
    GateEvidence,
)
from frost_core.effects import (
    EffectAuthorization,
    EffectConflict,
    EffectProtocolLedger,
    EffectRequest,
    EffectState,
    EffectTransitionError,
)
from frost_core.federation import (
    AdapterKind,
    AdapterStatus,
    default_federation_catalog,
)
from frost_core.provenance_miner import (
    EvidenceStrength,
    MinerQuery,
    ReadOnlyProvenanceMiner,
)
from frost_core.providers import (
    ProviderAvailability,
    ProviderMaturity,
    ProviderRecord,
    ProviderRegistry,
    RoutingPolicy,
)
from frost_core.reconciliation import (
    ControlPlaneSnapshot,
    ReconciliationLedger,
    ReconciliationState,
)
from frost_core.sdos import (
    ExperimentEvidence,
    ScientificBranchLedger,
    TheoryBranch,
    TheoryBranchStatus,
)
from frost_core.software_creation import (
    FrostV0Adapter,
    SoftwareRequest,
    V0Operation,
)


def _authorization(request: EffectRequest, *, approved: bool = True) -> EffectAuthorization:
    return EffectAuthorization(
        authorization_id="auth-1",
        request_sha256=request.sha256,
        capability=request.capability,
        actor="tester",
        approved=approved,
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )


def test_effect_full_lifecycle_and_audit(tmp_path: Path) -> None:
    ledger = EffectProtocolLedger(tmp_path / "effects.sqlite")
    request = EffectRequest("cloudflare.r2.apply", {"bucket": "demo"}, "key-1")
    effect_id, created = ledger.submit(request)
    assert created
    assert ledger.authorize(effect_id, _authorization(request)) == EffectState.AUTHORIZED

    claim = ledger.claim("worker-a", lease_seconds=60)
    assert claim is not None and claim.effect_id == effect_id
    token = ledger.begin_execution(
        claim,
        provider_id="cloudflare",
        provider_idempotency_key="cf:key-1",
        operation="r2.apply",
    )
    assert ledger.record_execution(
        effect_id,
        token,
        {"changed": True},
        {"request_id": "cf-123"},
    ) == EffectState.EXECUTED
    assert ledger.verify(
        effect_id,
        verifier_id="postcondition-v1",
        passed=True,
        evidence={"bucket_exists": True},
        independent=True,
    ) == EffectState.VERIFIED
    assert ledger.publish(effect_id, {"result_ref": "sha256:abc"}) == EffectState.PUBLISHED
    assert ledger.acknowledge(effect_id, {"delivery_id": "ack-1"}) == EffectState.ACKNOWLEDGED
    assert ledger.snapshot(effect_id).state == EffectState.ACKNOWLEDGED
    assert ledger.verify_audit_chain()


def test_effect_idempotency_and_conflict(tmp_path: Path) -> None:
    ledger = EffectProtocolLedger(tmp_path / "effects.sqlite")
    request = EffectRequest("x", {"v": 1}, "stable-key", request_id="req-1")
    first, created = ledger.submit(request)
    second, created_again = ledger.submit(request)
    assert first == second
    assert created
    assert not created_again
    with pytest.raises(EffectConflict):
        ledger.submit(replace(request, payload={"v": 2}))


def test_effect_denied_authorization_cannot_claim(tmp_path: Path) -> None:
    ledger = EffectProtocolLedger(tmp_path / "effects.sqlite")
    request = EffectRequest("external.write", {}, "key")
    effect_id, _ = ledger.submit(request)
    assert (
        ledger.authorize(effect_id, _authorization(request, approved=False))
        == EffectState.DENIED
    )
    assert ledger.claim("worker") is None


def test_effect_expired_claim_before_execution_is_retryable(tmp_path: Path) -> None:
    ledger = EffectProtocolLedger(tmp_path / "effects.sqlite")
    request = EffectRequest("external.write", {}, "key")
    effect_id, _ = ledger.submit(request)
    ledger.authorize(effect_id, _authorization(request))
    claim = ledger.claim("worker", lease_seconds=1)
    assert claim is not None
    future = datetime.now(UTC) + timedelta(seconds=2)
    assert ledger.recover_expired_claims(future) == 1
    assert ledger.snapshot(effect_id).state == EffectState.FAILED_RETRYABLE


def test_effect_crash_after_execution_intent_requires_reconciliation(tmp_path: Path) -> None:
    ledger = EffectProtocolLedger(tmp_path / "effects.sqlite")
    request = EffectRequest("external.write", {}, "key")
    effect_id, _ = ledger.submit(request)
    ledger.authorize(effect_id, _authorization(request))
    claim = ledger.claim("worker", lease_seconds=1)
    assert claim is not None
    token = ledger.begin_execution(
        claim,
        provider_id="provider",
        provider_idempotency_key="provider-key",
        operation="write",
    )
    assert ledger.recover_expired_claims(datetime.now(UTC) + timedelta(seconds=2)) == 1
    assert ledger.snapshot(effect_id).state == EffectState.RECOVERY_REQUIRED
    assert ledger.reconcile_execution(
        effect_id,
        execution_token=token,
        provider_status="UNKNOWN",
    ) == EffectState.RECOVERY_REQUIRED
    assert ledger.reconcile_execution(
        effect_id,
        execution_token=token,
        provider_status="EXECUTED",
        result={"ok": True},
        provider_receipt={"id": "provider-result"},
    ) == EffectState.EXECUTED


def test_effect_verifier_must_be_independent(tmp_path: Path) -> None:
    ledger = EffectProtocolLedger(tmp_path / "effects.sqlite")
    request = EffectRequest("external.write", {}, "key")
    effect_id, _ = ledger.submit(request)
    ledger.authorize(effect_id, _authorization(request))
    claim = ledger.claim("worker")
    assert claim is not None
    token = ledger.begin_execution(
        claim,
        provider_id="provider",
        provider_idempotency_key="provider-key",
        operation="write",
    )
    ledger.record_execution(effect_id, token, {"ok": True}, {"id": "receipt"})
    assert ledger.verify(
        effect_id,
        verifier_id="same-worker",
        passed=True,
        evidence={},
        independent=False,
    ) == EffectState.VERIFICATION_FAILED
    with pytest.raises(EffectTransitionError):
        ledger.publish(effect_id, {"result": "x"})


def test_effect_claim_concurrency_selects_once(tmp_path: Path) -> None:
    ledger = EffectProtocolLedger(tmp_path / "effects.sqlite")
    request = EffectRequest("external.write", {}, "key")
    effect_id, _ = ledger.submit(request)
    ledger.authorize(effect_id, _authorization(request))
    claims = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        claim = ledger.claim(f"worker-{index}")
        if claim is not None:
            with lock:
                claims.append(claim)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(claims) == 1


def test_provider_router_requires_explicit_policy_and_filters(tmp_path: Path) -> None:
    registry = ProviderRegistry(tmp_path / "providers.sqlite")
    registry.upsert(
        ProviderRecord(
            "github",
            "github-actions",
            ("frost.call",),
            ProviderMaturity.CONNECTED_VALIDATED,
            ProviderAvailability.AVAILABLE,
            source_identity="sha256:a",
            health=1.0,
            latency_ms=500,
            cost_rank=1,
        )
    )
    registry.upsert(
        ProviderRecord(
            "termux",
            "termux",
            ("frost.call",),
            ProviderMaturity.DEVICE_VALIDATED,
            ProviderAvailability.AVAILABLE,
            source_identity="sha256:b",
            health=0.9,
            latency_ms=20,
            cost_rank=1,
        )
    )
    decision = registry.select(
        "frost.call",
        RoutingPolicy(preferred_provider_ids=("github", "termux")),
    )
    assert decision.provider.provider_id == "github"
    decision = registry.select(
        "frost.call",
        RoutingPolicy(
            minimum_maturity=ProviderMaturity.DEVICE_VALIDATED,
            preferred_provider_ids=("github", "termux"),
        ),
    )
    assert decision.provider.provider_id == "termux"


def test_capability_factory_requires_every_gate(tmp_path: Path) -> None:
    ledger = CapabilityFactoryLedger(tmp_path / "factory.sqlite")
    candidate = CapabilityCandidate(
        "cap-1",
        "system.health",
        "sha256:source",
        "sha256:adapter",
        "read_only",
        "github",
        "sha256:schema",
    )
    assert ledger.discover(candidate) == CapabilityStage.DISCOVERED
    for stage in (
        CapabilityStage.WRAPPED,
        CapabilityStage.BUILDABLE,
        CapabilityStage.TESTED,
        CapabilityStage.DEPLOYED,
    ):
        assert ledger.advance_structural("cap-1", stage) == stage
    for gate in REQUIRED_PROMOTION_GATES[:-1]:
        ledger.record_gate("cap-1", GateEvidence(gate, True, {"ok": True}))
    decision = ledger.evaluate("cap-1")
    assert decision.new_stage != CapabilityStage.PROMOTED
    ledger.record_gate(
        "cap-1", GateEvidence(REQUIRED_PROMOTION_GATES[-1], True, {"receipt": "ok"})
    )
    assert ledger.evaluate("cap-1").new_stage == CapabilityStage.PROMOTED


def test_capability_factory_rejects_remote_shell(tmp_path: Path) -> None:
    ledger = CapabilityFactoryLedger(tmp_path / "factory.sqlite")
    with pytest.raises(ValueError):
        ledger.discover(
            CapabilityCandidate(
                "bad",
                "shell.exec",
                "source",
                "adapter",
                "remote_shell",
                "provider",
                "schema",
            )
        )


def test_provenance_miner_hash_match_and_safe_nested_zip(tmp_path: Path) -> None:
    target = b"canonical payload"
    digest = hashlib.sha256(target).hexdigest()
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("safe/payload.txt", target)
        archive.writestr("../unsafe.txt", b"must not inspect")
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as archive:
        archive.writestr("nested.zip", inner.getvalue())
    miner = ReadOnlyProvenanceMiner(max_depth=3)
    report = miner.scan([tmp_path], MinerQuery(expected_sha256=(digest,)))
    assert any(finding.strength == EvidenceStrength.HASH_MATCH for finding in report.findings)
    assert report.skipped_unsafe_members == 1


def test_reconciliation_requires_immutable_evidence_and_readback(tmp_path: Path) -> None:
    ledger = ReconciliationLedger(tmp_path / "reconcile.sqlite")
    snapshot = ControlPlaneSnapshot(
        "base44",
        "worker",
        "worker-1",
        desired={"state": "PROMOTED", "provider": "github"},
        observed={"state": "BLOCKED", "provider": "github"},
        immutable_evidence_identity="sha256:result",
    )
    decision = ledger.evaluate(snapshot)
    assert decision.state == ReconciliationState.PENDING
    diverged = ledger.mark_applied(snapshot, {"state": "PROMOTED", "provider": "vercel"})
    assert diverged.state == ReconciliationState.DIVERGED
    applied = ledger.mark_applied(snapshot, snapshot.desired)
    assert applied.state == ReconciliationState.APPLIED


class _FakeSoftwareProvider:
    provider_id = "fake-v0"

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, operation: V0Operation, arguments: dict, idempotency_key: str) -> dict:
        self.calls += 1
        return {
            "operation": operation.value,
            "arguments": arguments,
            "idempotency_key": idempotency_key,
        }


def test_v0_adapter_idempotency_and_pr_authority_separation() -> None:
    provider = _FakeSoftwareProvider()
    adapter = FrostV0Adapter(provider)
    request = SoftwareRequest(V0Operation.CREATE, {"prompt": "app"}, "r1", "k1")
    first = adapter.invoke(request)
    second = adapter.invoke(request)
    assert first == second
    assert provider.calls == 1
    prepared = adapter.prepare_pr(
        repository="owner/repo",
        base_branch="main",
        head_branch="agent/generated",
        title="Generated app",
        body="Prepared by software creation plane",
        changed_paths=["app/page.tsx", "app/page.tsx", "README.md"],
        source_result=first,
    )
    assert not prepared.github_write_authorized
    assert prepared.changed_paths == ("README.md", "app/page.tsx")


def test_sdos_preserves_falsified_branch(tmp_path: Path) -> None:
    ledger = ScientificBranchLedger(tmp_path / "sdos.sqlite")
    branch = TheoryBranch(
        branch_id="B1",
        mathematical_definition="V(phi)=phi^2/2",
        assumptions=("slow-roll",),
        parameters={"m": 1.0},
        observable_map={"r": "16 epsilon"},
        implementation_identity="sha256:impl",
        falsification_criteria=("r outside preregistered interval",),
    )
    ledger.add_branch(branch)
    evidence = ExperimentEvidence(
        experiment_id="E1",
        branch_sha256=branch.sha256,
        implementation_sha256="sha256:impl",
        inputs_sha256="sha256:inputs",
        result={"r": 0.09},
        verification={"passed": True},
        falsified=True,
        verifier_independent=True,
    )
    ledger.record_experiment("B1", evidence)
    assert ledger.classify_from_evidence("B1", "E1") == TheoryBranchStatus.REJECTED
    assert ledger.branch("B1")["current_status"] == "REJECTED"
    assert len(ledger.history("B1")) == 2


def test_federation_catalog_does_not_equate_membership_with_configuration() -> None:
    catalog = default_federation_catalog()
    assert catalog.get("openai").status == AdapterStatus.NOT_CONFIGURED
    connected = catalog.discover(minimum_status=AdapterStatus.CONNECTED_VALIDATED)
    assert {item.adapter_id for item in connected} == {"github-actions"}
    messaging = catalog.discover(kind=AdapterKind.MESSAGING)
    assert {item.adapter_id for item in messaging} == {
        "matrix",
        "mqtt",
        "nats",
        "websocket",
        "zeromq",
    }
