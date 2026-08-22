from frost_core.improvement_controller import (
    CanonicalImprovementState,
    ImprovementController,
    LifecycleGate,
    LifecycleStage,
    WorkCandidate,
)


def test_reconcile_deduplicates_and_filters_completed_blocked_and_dependencies():
    state = CanonicalImprovementState(completed={"done"})
    candidates = [
        WorkCandidate("dup", "cap.a", expected_value=1),
        WorkCandidate("dup", "cap.a", expected_value=5),
        WorkCandidate("done", "cap.done", expected_value=100),
        WorkCandidate("blocked", "cap.b", expected_value=100, blocked_reason="physical"),
        WorkCandidate("dep", "cap.c", expected_value=100, dependencies=("missing",)),
    ]
    result = ImprovementController.reconcile(candidates, state)
    assert [c.candidate_id for c in result] == ["dup"]
    assert result[0].expected_value == 5


def test_rank_prefers_dependency_unlock_and_human_labor_reduction():
    state = CanonicalImprovementState()
    candidates = [
        WorkCandidate("feature", "cap.feature", expected_value=10),
        WorkCandidate(
            "platform",
            "cap.platform",
            expected_value=4,
            dependency_unlock=5,
            human_labor_reduction=3,
        ),
    ]
    ranked = ImprovementController.rank(candidates, state)
    assert ranked[0].candidate.candidate_id == "platform"


def test_rank_tie_break_is_deterministic():
    state = CanonicalImprovementState()
    candidates = [WorkCandidate("b", "cap"), WorkCandidate("a", "cap")]
    result = ImprovementController.rank(candidates, state)
    assert [x.candidate.candidate_id for x in result] == ["a", "b"]


def test_lifecycle_gate_fails_closed_without_evidence():
    state = CanonicalImprovementState()
    assert ImprovementController.attempt_promotion(state) == LifecycleStage.PROPOSED
    state.evidence.add("implementation_artifact")
    assert ImprovementController.attempt_promotion(state) == LifecycleStage.IMPLEMENTED
    assert ImprovementController.attempt_promotion(state) == LifecycleStage.IMPLEMENTED


def test_lifecycle_requires_independent_verification_before_verified():
    state = CanonicalImprovementState(
        lifecycle_stage=LifecycleStage.TESTED,
        evidence={"implementation_artifact", "tests_pass"},
    )
    assert ImprovementController.attempt_promotion(state) == LifecycleStage.TESTED
    state.evidence.add("independent_verification")
    assert ImprovementController.attempt_promotion(state) == LifecycleStage.INDEPENDENTLY_VERIFIED


def test_device_and_persistence_are_distinct():
    evidence = {
        "implementation_artifact",
        "tests_pass",
        "independent_verification",
        "device_origin",
    }
    assert (
        LifecycleGate.promote(LifecycleStage.INDEPENDENTLY_VERIFIED, evidence)
        == LifecycleStage.DEVICE_VALIDATED
    )
    assert (
        LifecycleGate.promote(LifecycleStage.DEVICE_VALIDATED, evidence)
        == LifecycleStage.DEVICE_VALIDATED
    )
    evidence |= {"changed_boot_id", "persistence_verification"}
    assert (
        LifecycleGate.promote(LifecycleStage.DEVICE_VALIDATED, evidence)
        == LifecycleStage.PERSISTENT_VALIDATED
    )


def test_record_completed_updates_state_without_granting_promotion():
    state = CanonicalImprovementState()
    ImprovementController.record_completed(
        state, "x", evidence={"implementation_artifact", "tests_pass"}
    )
    assert "x" in state.completed
    assert state.lifecycle_stage == LifecycleStage.PROPOSED
    assert ImprovementController.attempt_promotion(state) == LifecycleStage.IMPLEMENTED


def test_select_returns_none_at_true_boundary():
    state = CanonicalImprovementState(completed={"ready"})
    candidates = [
        WorkCandidate("blocked", "device.run", blocked_reason="device_action_required"),
        WorkCandidate("ready", "host.run"),
    ]
    assert ImprovementController.select(candidates, state) is None
