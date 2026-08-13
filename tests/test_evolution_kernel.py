from __future__ import annotations

from dataclasses import replace

import pytest

from centinal26.evolution_kernel import (
    CandidateGovernanceEvidence,
    EvolutionDecision,
    EvolutionKernelPolicy,
    GateDisposition,
    MetaPolicyConstraints,
    PersistenceEvidence,
    RiskClass,
    compute_envelope,
    govern_candidate,
    select_unique_active_envelope,
)

POLICY_HASH = "87a0074a844ee9a65bedc8f5d43c08767dec88964655936fa75e230ee43b5e9f"
EVIDENCE_HASH = "a793e41012759884a47487f0451438db036a23b21797453356ca74b826d0c888"


def meta_policy() -> MetaPolicyConstraints:
    return MetaPolicyConstraints(
        min_occurrences=2,
        min_confidence=0.90,
        max_auto_risk=RiskClass.LOW,
        require_deterministic_pass=True,
        require_rollback=True,
        allow_schema_mutation=False,
        allow_external_side_effects=False,
    )


def policy() -> EvolutionKernelPolicy:
    return EvolutionKernelPolicy(
        maturity_weights={
            "validation_stability": 0.25,
            "regression_resilience": 0.20,
            "environment_coverage": 0.15,
            "rollback_readiness": 0.15,
            "repeated_success": 0.15,
            "promotion_closure": 0.10,
        },
        uncertainty_weights={
            "evidence_gap": 0.35,
            "environment_gap": 0.30,
            "model_error": 0.20,
            "frontier_opportunity": 0.15,
        },
        mutation_floor=0.01,
        mutation_ceiling=0.20,
        annealing_rate=2.0,
        exploration_floor_fraction=0.10,
        confidence_floor=0.93,
        occurrence_floor=3,
        required_evidence_depth=3,
        regression_tolerances={
            "semantic_equivalence": 0.0,
            "failure_count": 0.0,
            "rollback_available": 0.0,
        },
        promotion_delta_min=0.05,
        branch_delta_min=0.15,
        niche_occurrence_min=3,
        niche_duration_min_days=14.0,
        niche_replication_min=2,
        max_effective_risk=RiskClass.LOW,
    )


def live_seed_envelope():
    return compute_envelope(
        capability_id="APB-CAP-0004",
        generation=0,
        maturity_components={
            "validation_stability": 0.75,
            "regression_resilience": 0.70,
            "environment_coverage": 0.25,
            "rollback_readiness": 1.00,
            "repeated_success": 0.50,
            "promotion_closure": 0.25,
        },
        uncertainty_components={
            "evidence_gap": 0.50,
            "environment_gap": 0.75,
            "model_error": 0.10,
            "frontier_opportunity": 0.23333333333333334,
        },
        policy=policy(),
        meta_policy=meta_policy(),
        source_meta_policy="meta-automation-v1",
        source_policy_hash=POLICY_HASH,
        source_evidence_hash=EVIDENCE_HASH,
    )


def candidate(
    *,
    deterministic_status: str | None = "PASS",
    evidence_depth: int = 3,
    semantic_delta: float = 0.0,
    current_gain: float = 0.08,
    niche_gain: float = 0.0,
    external_side_effects: bool = False,
) -> CandidateGovernanceEvidence:
    return CandidateGovernanceEvidence(
        candidate_id="fixture-candidate",
        authorized=True,
        risk_class=RiskClass.LOW,
        confidence=0.98,
        occurrence_count=4,
        evidence_depth=evidence_depth,
        rollback_defined=True,
        deterministic_status=deterministic_status,
        schema_mutation=False,
        external_side_effects=external_side_effects,
        protected_deltas={
            "semantic_equivalence": semantic_delta,
            "failure_count": 0.0,
            "rollback_available": 0.0,
        },
        current_fit_deltas={"gain": current_gain},
        current_fit_weights={"gain": 1.0},
        niche_fit_deltas={"niche_gain": niche_gain},
        niche_fit_weights={"niche_gain": 1.0},
        persistence=PersistenceEvidence(
            independent_occurrences=4,
            duration_days=21.0,
            independent_replications=3,
            median_advantage=0.20,
        ),
        low_switching_cost=False,
        high_coexistence_cost=False,
    )


def test_live_generation_zero_seed_is_reproducible() -> None:
    envelope = live_seed_envelope()
    assert envelope.maturity_score == pytest.approx(0.615)
    assert envelope.uncertainty_score == pytest.approx(0.455)
    assert envelope.effective_mutation_budget == pytest.approx(0.038295383)
    assert envelope.kernel_hash == policy().digest()


def test_policy_may_tighten_but_not_loosen_meta_policy() -> None:
    assert policy().respects(meta_policy())
    loosened = replace(policy(), confidence_floor=0.80, occurrence_floor=1)
    assert loosened.respects(meta_policy()) is False
    with pytest.raises(ValueError, match="loosens"):
        compute_envelope(
            capability_id="APB-CAP-0004",
            generation=0,
            maturity_components={
                "validation_stability": 0.75,
                "regression_resilience": 0.70,
                "environment_coverage": 0.25,
                "rollback_readiness": 1.00,
                "repeated_success": 0.50,
                "promotion_closure": 0.25,
            },
            uncertainty_components={
                "evidence_gap": 0.50,
                "environment_gap": 0.75,
                "model_error": 0.10,
                "frontier_opportunity": 0.23333333333333334,
            },
            policy=loosened,
            meta_policy=meta_policy(),
            source_meta_policy="meta-automation-v1",
            source_policy_hash=POLICY_HASH,
            source_evidence_hash=EVIDENCE_HASH,
        )


def test_missing_deterministic_validation_blocks_before_fit() -> None:
    evidence = candidate(deterministic_status=None, current_gain=1.0)
    result = govern_candidate(evidence, live_seed_envelope(), meta_policy())
    assert result.hard_valid is False
    assert result.fit_score is None
    assert result.decision is EvolutionDecision.REJECT_FROM_PROMOTION
    assert result.gate.disposition is GateDisposition.BLOCKED_PENDING_VALIDATION


def test_realistic_pass_still_needs_independent_evidence_depth() -> None:
    evidence = candidate(evidence_depth=1, current_gain=0.6529861601078487)
    result = govern_candidate(evidence, live_seed_envelope(), meta_policy())
    assert result.hard_valid is False
    assert result.gate.disposition is GateDisposition.BLOCKED_INSUFFICIENT_EVIDENCE


def test_valid_compatible_improvement_promotes() -> None:
    result = govern_candidate(candidate(), live_seed_envelope(), meta_policy())
    assert result.hard_valid is True
    assert result.compatible is True
    assert result.decision is EvolutionDecision.PROMOTE


def test_persistent_compatible_low_switching_niche_polymorphs() -> None:
    evidence = replace(
        candidate(current_gain=0.01, niche_gain=0.20),
        low_switching_cost=True,
    )
    result = govern_candidate(evidence, live_seed_envelope(), meta_policy())
    assert result.compatible is True
    assert result.persistent is True
    assert result.decision is EvolutionDecision.POLYMORPH


def test_incompatible_persistent_high_coexistence_niche_speciates() -> None:
    evidence = replace(
        candidate(semantic_delta=-0.02, current_gain=0.01, niche_gain=0.20),
        high_coexistence_cost=True,
    )
    result = govern_candidate(evidence, live_seed_envelope(), meta_policy())
    assert result.compatible is False
    assert result.persistent is True
    assert result.decision is EvolutionDecision.SPECIATE


def test_incompatible_niche_without_high_coexistence_cost_does_not_speciate() -> None:
    evidence = candidate(semantic_delta=-0.02, current_gain=0.01, niche_gain=0.20)
    result = govern_candidate(evidence, live_seed_envelope(), meta_policy())
    assert result.compatible is False
    assert result.decision is EvolutionDecision.REJECT_FROM_PROMOTION


def test_forbidden_external_side_effect_requires_human_review() -> None:
    evidence = candidate(external_side_effects=True, current_gain=1.0)
    result = govern_candidate(evidence, live_seed_envelope(), meta_policy())
    assert result.hard_valid is False
    assert result.gate.disposition is GateDisposition.HUMAN_REVIEW_REQUIRED
    assert result.fit_score is None


def test_single_active_lineage_is_fail_closed() -> None:
    active = {
        "capability_id": "APB-CAP-0004",
        "generation": 0,
        "status": "active",
    }
    superseded = {
        "capability_id": "APB-CAP-0004",
        "generation": 0,
        "status": "superseded",
    }
    assert (
        select_unique_active_envelope(
            [active, superseded],
            capability_id="APB-CAP-0004",
        )
        == active
    )
    with pytest.raises(ValueError, match="exactly one active envelope"):
        select_unique_active_envelope(
            [active, {**active, "generation": 1}],
            capability_id="APB-CAP-0004",
        )
