from __future__ import annotations

import pytest

from centinal26.evolution_kernel import (
    CandidateGovernanceEvidence,
    EvolutionDecision,
    EvolutionKernelPolicy,
    PersistenceEvidence,
    assert_unique_active_envelope,
    compute_envelope,
    govern_candidate,
)


def policy() -> EvolutionKernelPolicy:
    return EvolutionKernelPolicy(
        maturity_weights={
            "validation_stability": 0.30,
            "failure_resilience": 0.20,
            "environment_coverage": 0.15,
            "rollback_readiness": 0.15,
            "repeated_success": 0.10,
            "promotion_readiness": 0.10,
        },
        uncertainty_weights={
            "unresolved": 0.40,
            "environment_gap": 0.30,
            "calibration_gap": 0.20,
            "novelty": 0.10,
        },
        mutation_floor=0.01,
        mutation_ceiling=0.20,
        mutation_sensitivity=0.8501388235824324,
        confidence_floor=0.93,
        occurrence_floor=3,
        required_evidence_depth=3,
        promotion_delta_min=0.05,
        branch_delta_min=0.15,
        niche_occurrence_min=3,
        niche_duration_min_days=14.0,
        niche_replication_min=2,
        max_effective_risk="LOW",
    )


def live_seed_envelope():
    return compute_envelope(
        capability_id="APB-CAP-0004",
        generation=0,
        maturity_components={
            "validation_stability": 0.60,
            "failure_resilience": 0.80,
            "environment_coverage": 0.20,
            "rollback_readiness": 1.00,
            "repeated_success": 0.45,
            "promotion_readiness": 0.50,
        },
        uncertainty_components={
            "unresolved": 0.50,
            "environment_gap": 0.50,
            "calibration_gap": 0.40,
            "novelty": 0.25,
        },
        policy=policy(),
        source_meta_policy="meta-automation-v1",
        source_policy_hash="87a0074a844ee9a65bedc8f5d43c08767dec88964655936fa75e230ee43b5e9f",
        source_evidence_hash="a793e41012759884a47487f0451438db036a23b21797453356ca74b826d0c888",
    )


def test_live_generation_zero_seed_is_reproducible() -> None:
    envelope = live_seed_envelope()
    assert envelope.maturity_score == pytest.approx(0.615)
    assert envelope.uncertainty_score == pytest.approx(0.455)
    assert envelope.effective_mutation_budget == pytest.approx(0.038295383)
    assert envelope.kernel_hash == policy().digest()


def test_high_fitness_cannot_bypass_hard_validation() -> None:
    evidence = CandidateGovernanceEvidence(
        hard_valid=False,
        fit_score=0.41978,
        niche_fit_score=0.41978,
        protected_regressions={
            "semantic_equivalence": 0.0,
            "failure_count": 0.0,
            "rollback_available": 0.0,
        },
        regression_tolerances={
            "semantic_equivalence": 0.0,
            "failure_count": 0.0,
            "rollback_available": 0.0,
        },
        persistence=PersistenceEvidence(1, 0.0, 1),
    )
    result = govern_candidate(evidence, policy())
    assert result.hard_valid is False
    assert result.compatible is False
    assert result.decision is EvolutionDecision.REJECT_FROM_PROMOTION
    assert "hard_validation_failed" in result.reasons


def test_valid_global_improvement_promotes() -> None:
    evidence = CandidateGovernanceEvidence(
        hard_valid=True,
        fit_score=0.10,
        niche_fit_score=0.02,
        protected_regressions={"semantic_equivalence": 0.0},
        regression_tolerances={"semantic_equivalence": 0.0},
        persistence=PersistenceEvidence(1, 1.0, 1),
    )
    result = govern_candidate(evidence, policy())
    assert result.compatible is True
    assert result.persistent is False
    assert result.decision is EvolutionDecision.PROMOTE


def test_persistent_niche_can_polymorph() -> None:
    evidence = CandidateGovernanceEvidence(
        hard_valid=True,
        fit_score=0.03,
        niche_fit_score=0.10,
        protected_regressions={"semantic_equivalence": 0.0},
        regression_tolerances={"semantic_equivalence": 0.0},
        persistence=PersistenceEvidence(3, 14.0, 2),
    )
    result = govern_candidate(evidence, policy())
    assert result.persistent is True
    assert result.decision is EvolutionDecision.POLYMORPH


def test_persistent_strong_niche_can_speciate() -> None:
    evidence = CandidateGovernanceEvidence(
        hard_valid=True,
        fit_score=0.03,
        niche_fit_score=0.20,
        protected_regressions={"semantic_equivalence": 0.0},
        regression_tolerances={"semantic_equivalence": 0.0},
        persistence=PersistenceEvidence(4, 20.0, 3),
    )
    result = govern_candidate(evidence, policy())
    assert result.persistent is True
    assert result.decision is EvolutionDecision.SPECIATE


def test_protected_metric_regression_blocks_promotion() -> None:
    evidence = CandidateGovernanceEvidence(
        hard_valid=True,
        fit_score=1.0,
        niche_fit_score=1.0,
        protected_regressions={"failure_count": 1.0},
        regression_tolerances={"failure_count": 0.0},
        persistence=PersistenceEvidence(10, 100.0, 10),
    )
    result = govern_candidate(evidence, policy())
    assert result.compatible is False
    assert result.decision is EvolutionDecision.REJECT_FROM_PROMOTION


def test_active_envelope_lineage_is_singleton() -> None:
    assert_unique_active_envelope(
        [
            {"capability_id": "APB-CAP-0004", "generation": 0, "status": "active"},
            {"capability_id": "APB-CAP-0004", "generation": 0, "status": "superseded"},
        ],
        capability_id="APB-CAP-0004",
        generation=0,
    )


def test_duplicate_active_envelope_is_rejected() -> None:
    with pytest.raises(ValueError, match="multiple active envelopes"):
        assert_unique_active_envelope(
            [
                {"capability_id": "APB-CAP-0004", "generation": 0, "status": "active"},
                {"capability_id": "APB-CAP-0004", "generation": 0, "status": "active"},
            ],
            capability_id="APB-CAP-0004",
            generation=0,
        )
