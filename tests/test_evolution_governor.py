from dataclasses import replace

import pytest

from frost_core.evolution_governor import (
    AdaptiveEvolutionGovernor,
    CandidateEvidence,
    EvolutionDisposition,
    EvolutionEnvelope,
    GateDisposition,
    MaturityInputs,
    MetaPolicy,
    NicheEvidence,
    RiskClass,
    UncertaintyInputs,
    maturity_score,
    mutation_budget,
    select_active_envelope,
    uncertainty_score,
)


def policy() -> MetaPolicy:
    return MetaPolicy(
        min_occurrences=2,
        min_confidence=0.90,
        max_auto_risk=RiskClass.LOW,
        require_deterministic_pass=True,
        require_rollback=True,
        allow_schema_mutation=False,
        allow_external_side_effects=False,
    )


def envelope() -> EvolutionEnvelope:
    return EvolutionEnvelope(
        capability_id="APB-CAP-0004",
        generation=0,
        maturity_score=0.615,
        uncertainty_score=0.455,
        mutation_floor=0.01,
        mutation_ceiling=0.20,
        effective_mutation_budget=0.038295383,
        confidence_floor=0.93,
        occurrence_floor=3,
        max_effective_risk=RiskClass.LOW,
        required_evidence_depth=3,
        regression_tolerances={
            "semantic_equivalence": 0.0,
            "failure_count": 0.0,
            "rollback_available": 0.0,
        },
        promotion_delta_min=0.05,
        branch_delta_min=0.15,
        niche_occurrence_min=3,
        niche_duration_days_min=14.0,
        niche_replication_min=2,
        source_meta_policy="meta-automation-v1",
    )


def real_host_candidate(*, deterministic_status: str | None, evidence_depth: int = 1) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id="APB-EXP-0002:concurrency-4",
        authorized=True,
        risk_class=RiskClass.LOW,
        confidence=0.98,
        occurrence_count=10,
        evidence_depth=evidence_depth,
        rollback_defined=True,
        deterministic_status=deterministic_status,
        protected_deltas={
            "semantic_equivalence": 0.0,
            "failure_count": 0.0,
            "rollback_available": 0.0,
        },
        current_fit_deltas={
            "wall_clock_reduction": 0.6529861601078487,
            "semantic_delta": 0.0,
            "failure_delta": 0.0,
            "calibration_delta": -0.09317254513433963,
        },
        current_fit_weights={
            "wall_clock_reduction": 0.65,
            "semantic_delta": 0.20,
            "failure_delta": 0.10,
            "calibration_delta": 0.05,
        },
    )


def test_active_live_seed_is_reproducible() -> None:
    maturity = maturity_score(
        MaturityInputs(
            validation_stability=0.75,
            regression_resilience=0.70,
            environment_coverage=0.25,
            rollback_readiness=1.0,
            repeated_success=0.50,
            promotion_closure=0.25,
        )
    )
    uncertainty = uncertainty_score(
        UncertaintyInputs(
            evidence_gap=0.50,
            environment_gap=0.75,
            model_error=0.10,
            frontier_opportunity=0.23333333333333334,
        )
    )

    assert maturity == 0.615
    assert uncertainty == 0.455
    assert mutation_budget(
        mutation_floor=0.01,
        mutation_ceiling=0.20,
        maturity=maturity,
        uncertainty=uncertainty,
    ) == 0.038295383


def test_derived_envelope_may_tighten_but_not_loosen_meta_policy() -> None:
    current = envelope()
    assert current.respects(policy())
    assert not replace(current, confidence_floor=0.80).respects(policy())
    assert not replace(current, occurrence_floor=1).respects(policy())
    assert not replace(current, max_effective_risk=RiskClass.MEDIUM).respects(policy())


def test_single_active_lineage_is_fail_closed() -> None:
    current = envelope()
    assert select_active_envelope(current.capability_id, [current]) == current
    with pytest.raises(ValueError, match="exactly one active envelope"):
        select_active_envelope(current.capability_id, [current, replace(current, generation=1)])


def test_real_candidate_is_blocked_when_deterministic_validation_is_missing() -> None:
    decision = AdaptiveEvolutionGovernor().decide(
        real_host_candidate(deterministic_status=None), envelope(), policy()
    )
    assert decision.disposition is EvolutionDisposition.REJECT_FROM_PROMOTION
    assert decision.gate.disposition is GateDisposition.BLOCKED_PENDING_VALIDATION
    assert decision.hard_valid is False
    assert decision.current_fit is None


def test_real_candidate_still_needs_independent_evidence_depth_after_pass() -> None:
    decision = AdaptiveEvolutionGovernor().decide(
        real_host_candidate(deterministic_status="PASS"), envelope(), policy()
    )
    assert decision.disposition is EvolutionDisposition.REJECT_FROM_PROMOTION
    assert decision.gate.disposition is GateDisposition.BLOCKED_INSUFFICIENT_EVIDENCE
    assert "evidence depth" in decision.gate.reasons[0]


def qualified_candidate(*, semantic_delta: float = 0.0) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id="fixture-qualified",
        authorized=True,
        risk_class=RiskClass.LOW,
        confidence=0.98,
        occurrence_count=4,
        evidence_depth=3,
        rollback_defined=True,
        deterministic_status="PASS",
        protected_deltas={
            "semantic_equivalence": semantic_delta,
            "failure_count": 0.0,
            "rollback_available": 0.0,
        },
        current_fit_deltas={"gain": 0.08},
        current_fit_weights={"gain": 1.0},
    )


def persistent_niche(*, switching: bool, coexistence: bool) -> NicheEvidence:
    return NicheEvidence(
        occurrences=4,
        duration_days=21.0,
        replications=3,
        median_advantage=0.20,
        fit_deltas={"niche_gain": 0.20},
        fit_weights={"niche_gain": 1.0},
        low_switching_cost=switching,
        high_coexistence_cost=coexistence,
    )


def test_qualified_compatible_candidate_reaches_promotion_branch() -> None:
    decision = AdaptiveEvolutionGovernor().decide(qualified_candidate(), envelope(), policy())
    assert decision.disposition is EvolutionDisposition.PROMOTION_CANDIDATE
    assert decision.compatible is True


def test_persistent_compatible_niche_can_become_polymorph() -> None:
    candidate = replace(qualified_candidate(), current_fit_deltas={"gain": 0.01})
    decision = AdaptiveEvolutionGovernor().decide(
        candidate,
        envelope(),
        policy(),
        persistent_niche(switching=True, coexistence=False),
    )
    assert decision.disposition is EvolutionDisposition.POLYMORPH_CANDIDATE


def test_speciation_requires_persistent_incompatibility_and_high_coexistence_cost() -> None:
    candidate = replace(
        qualified_candidate(semantic_delta=-0.02),
        current_fit_deltas={"gain": 0.01},
    )
    governor = AdaptiveEvolutionGovernor()
    held = governor.decide(
        candidate,
        envelope(),
        policy(),
        persistent_niche(switching=False, coexistence=False),
    )
    branched = governor.decide(
        candidate,
        envelope(),
        policy(),
        persistent_niche(switching=False, coexistence=True),
    )
    assert held.disposition is EvolutionDisposition.REJECT_FROM_PROMOTION
    assert branched.disposition is EvolutionDisposition.SPECIATION_CANDIDATE
    assert branched.compatible is False


def test_unauthorized_or_forbidden_side_effect_candidate_never_passes_hard_valid() -> None:
    governor = AdaptiveEvolutionGovernor()
    unauthorized = governor.decide(
        replace(qualified_candidate(), authorized=False), envelope(), policy()
    )
    side_effect = governor.decide(
        replace(qualified_candidate(), external_side_effects=True), envelope(), policy()
    )
    assert unauthorized.gate.disposition is GateDisposition.BLOCKED_UNAUTHORIZED
    assert side_effect.gate.disposition is GateDisposition.HUMAN_REVIEW_REQUIRED
