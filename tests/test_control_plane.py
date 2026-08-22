from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from centinal26.control_plane import (
    Checkpoint,
    CircuitBreaker,
    CircuitState,
    DebtPolicy,
    DebtState,
    EvidenceRecord,
    ExecutionMode,
    MutationContract,
    OperationLedger,
    Phase,
    PromotionClaim,
    ReentrancyGuard,
    RevalidationPolicy,
    SagaRunner,
    SagaState,
    SagaStep,
    canonical_sha256,
    hourly_epoch,
    prove_mutation,
    prove_promotion,
)

NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


def evidence(
    kind: str,
    *,
    evidence_id: str | None = None,
    subject: str | None = None,
    acquired_at: datetime = NOW,
    ttl_seconds: int = 300,
    provenance: str = "external",
    run_id: str = "verify-run",
) -> EvidenceRecord:
    subjects = {
        "authority": "guardian-policy-v1",
        "identity": "centinal26-controller",
        "target": "repo:12ephods-source/centinal26",
        "preconditions": "repo:12ephods-source/centinal26",
    }
    return EvidenceRecord(
        evidence_id=evidence_id or f"e-{kind}",
        kind=kind,
        subject=subject or subjects.get(kind, "repo:12ephods-source/centinal26"),
        source="github",
        acquired_at=acquired_at.isoformat(),
        ttl_seconds=ttl_seconds,
        digest=canonical_sha256({"kind": kind, "at": acquired_at.isoformat()}),
        provenance=provenance,
        run_id=run_id,
        epoch=hourly_epoch(acquired_at),
    )


def contract() -> MutationContract:
    return MutationContract(
        operation_id="op-1",
        authority="guardian-policy-v1",
        actor_identity="centinal26-controller",
        target_identity="repo:12ephods-source/centinal26",
        preconditions=("main_head_matches", "repo_clean"),
        blast_radius=2,
        rollback_plan="restore previous refs and compensate provider mutation",
        postconditions=("branch_head_matches", "provider_state_matches"),
        idempotency_key="op-1:main:a038",
        evidence_required=("authority", "identity", "target", "preconditions"),
        canary_supported=True,
    )


def test_mutation_proof_requires_fresh_complete_evidence_and_selects_canary(tmp_path) -> None:
    records = [evidence(kind) for kind in contract().evidence_required]
    result = prove_mutation(
        contract(),
        records,
        {"main_head_matches": True, "repo_clean": True},
        now=NOW + timedelta(seconds=10),
        ledger=OperationLedger(tmp_path / "ledger.json"),
    )
    assert result.passed
    assert result.execution_mode == ExecutionMode.CANARY

    stale = [
        evidence(kind, acquired_at=NOW - timedelta(hours=2), ttl_seconds=60)
        for kind in contract().evidence_required
    ]
    blocked = prove_mutation(
        contract(),
        stale,
        {"main_head_matches": True, "repo_clean": True},
        now=NOW,
    )
    assert not blocked.passed
    assert "evidence_stale:target" in blocked.reasons


def test_mutation_proof_binds_authority_actor_and_target_identity() -> None:
    records = [evidence(kind) for kind in contract().evidence_required]
    records[1] = evidence("identity", subject="different-controller")
    result = prove_mutation(
        contract(),
        records,
        {"main_head_matches": True, "repo_clean": True},
        now=NOW,
    )
    assert not result.passed
    assert "evidence_subject_mismatch:identity" in result.reasons


def test_evidence_epoch_must_match_acquisition_time() -> None:
    with pytest.raises(ValueError, match="epoch must match"):
        EvidenceRecord(
            evidence_id="bad-epoch",
            kind="target",
            subject="repo:12ephods-source/centinal26",
            source="github",
            acquired_at=NOW.isoformat(),
            ttl_seconds=300,
            digest="a" * 64,
            provenance="external",
            run_id="verify-run",
            epoch=hourly_epoch(NOW) + 1,
        )


def test_idempotency_ledger_fails_closed_on_replay_and_conflict(tmp_path) -> None:
    ledger = OperationLedger(tmp_path / "ledger.json")
    ledger.record("key", "a" * 64)
    ledger.record("key", "a" * 64)
    with pytest.raises(ValueError, match="different result"):
        ledger.record("key", "b" * 64)

    replay_contract = replace(contract(), idempotency_key="key")
    result = prove_mutation(
        replay_contract,
        [evidence(kind) for kind in replay_contract.evidence_required],
        {"main_head_matches": True, "repo_clean": True},
        now=NOW,
        ledger=ledger,
    )
    assert not result.passed
    assert "idempotency_key_already_committed" in result.reasons


def test_backpressure_blocks_build_and_evolve_but_not_verify_or_recover() -> None:
    state = DebtState(verification_debt=2, deployment_debt=1)
    policy = DebtPolicy(max_verification_debt=0, max_deployment_debt=0)
    for phase in (Phase.BUILD, Phase.EVOLVE):
        allowed, reasons = state.permits(phase, policy)
        assert not allowed
        assert set(reasons) == {"verification_debt", "deployment_debt"}
    for phase in (Phase.VERIFY, Phase.RECOVER):
        assert state.permits(phase, policy) == (True, ())


def test_circuit_breaker_opens_half_opens_and_recovers() -> None:
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
    assert breaker.allow(NOW)
    breaker.failure(NOW)
    assert breaker.state == CircuitState.CLOSED
    breaker.failure(NOW)
    assert breaker.state == CircuitState.OPEN
    assert not breaker.allow(NOW + timedelta(seconds=59))
    assert breaker.allow(NOW + timedelta(seconds=60))
    assert breaker.state == CircuitState.HALF_OPEN
    assert not breaker.allow(NOW + timedelta(seconds=61))
    breaker.success()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.allow(NOW + timedelta(seconds=62))


def test_checkpoint_resume_digest_is_stable_and_detects_state_drift() -> None:
    checkpoint = Checkpoint.create(
        run_id="run-a",
        epoch=hourly_epoch(NOW),
        phase=Phase.VERIFY,
        immutable_inputs={"commit": "abc", "contract": "def"},
        result_digests=["b", "a"],
        pending_obligations=["external-evidence", "postconditions"],
        state={"cursor": 7},
    )
    same = Checkpoint.create(
        run_id="run-a",
        epoch=hourly_epoch(NOW),
        phase=Phase.VERIFY,
        immutable_inputs={"contract": "def", "commit": "abc"},
        result_digests=["a", "b"],
        pending_obligations=["postconditions", "external-evidence"],
        state={"cursor": 7},
    )
    assert checkpoint.resume_digest == same.resume_digest
    assert checkpoint.verify()
    checkpoint.assert_resume(
        {"commit": "abc", "contract": "def"},
        {"cursor": 7},
    )
    with pytest.raises(ValueError, match="restored state"):
        checkpoint.assert_resume(
            {"commit": "abc", "contract": "def"},
            {"cursor": 8},
        )


def test_promotion_requires_distinct_later_epoch_and_fresh_external_evidence() -> None:
    external = evidence(
        "verification",
        evidence_id="github-checks",
        acquired_at=NOW + timedelta(hours=1),
        ttl_seconds=3600,
        provenance="external",
        run_id="run-b",
    )
    claim = PromotionClaim(
        result_digest="a" * 64,
        build_run_id="run-a",
        build_epoch=hourly_epoch(NOW),
        verification_run_id="run-b",
        verification_epoch=hourly_epoch(NOW + timedelta(hours=1)),
        external_evidence_ids=("github-checks",),
    )
    assert prove_promotion(
        claim,
        [external],
        now=NOW + timedelta(hours=1, minutes=5),
    ).passed

    same_epoch = replace(
        claim,
        verification_run_id="run-a",
        verification_epoch=claim.build_epoch,
    )
    result = prove_promotion(same_epoch, [external], now=NOW + timedelta(hours=1))
    assert not result.passed
    assert "verification_must_cross_hourly_epoch" in result.reasons
    assert "verification_must_use_distinct_run" in result.reasons


def test_saga_compensates_successful_steps_in_reverse_order() -> None:
    events: list[str] = []

    def step(name: str, passes: bool) -> SagaStep:
        def forward() -> str:
            events.append(f"forward:{name}")
            return name

        def postcondition(_: str) -> bool:
            return passes

        def compensate(_: str) -> str:
            events.append(f"compensate:{name}")
            return name

        return SagaStep(
            name=name,
            forward=forward,
            postcondition=postcondition,
            compensate=compensate,
            compensation_postcondition=lambda value: value == name,
        )

    result = SagaRunner().execute([step("github", True), step("base44", False)])
    assert result.state == SagaState.COMPENSATED
    assert result.completed == ("github",)
    assert result.compensated == ("github",)
    assert events == ["forward:github", "forward:base44", "compensate:github"]


def test_reentrancy_guard_blocks_overlap_and_reclaims_stale_lease(tmp_path) -> None:
    path = tmp_path / "controller.lock"
    first = ReentrancyGuard(path, "run-a", lease_seconds=60)
    first.acquire(NOW)
    second = ReentrancyGuard(path, "run-b", lease_seconds=60)
    with pytest.raises(RuntimeError, match="reentrancy_blocked"):
        second.acquire(NOW + timedelta(seconds=30))
    first.release()

    path.write_text(
        json.dumps(
            {
                "run_id": "crashed",
                "pid": 999,
                "acquired_at": (NOW - timedelta(minutes=5)).isoformat(),
                "lease_seconds": 60,
            }
        ),
        encoding="utf-8",
    )
    second.acquire(NOW)
    assert json.loads(path.read_text(encoding="utf-8"))["run_id"] == "run-b"
    second.release()


def test_risk_weighted_revalidation_is_more_frequent_for_high_blast_radius() -> None:
    policy = RevalidationPolicy()
    last = (NOW - timedelta(hours=7)).isoformat()
    assert not policy.due(last, blast_radius=0, now=NOW)
    assert policy.due(last, blast_radius=3, now=NOW)


def test_control_plane_schemas_are_strict_draft_2020_12_objects() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = {
        "mutation_contract.schema.json": "centinal26-mutation-contract-v1",
        "evidence_record.schema.json": "centinal26-evidence-record-v1",
        "checkpoint.schema.json": "centinal26-checkpoint-v1",
        "component_state.schema.json": "centinal26-component-state-v1",
    }
    for name, schema_id in expected.items():
        schema = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["properties"]["schema"]["const"] == schema_id
