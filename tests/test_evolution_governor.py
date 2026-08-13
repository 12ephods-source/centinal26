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
    maturity_score,
    mutation_budget,
    uncertainty_score,
)


def policy() -> MetaPolicy:
    return MetaPolicy(
        min_occurrences=2,
        min_confidence=0.90,
        max_auto_risk=RiskClass.LOW,
        require_deterministic_pass=True,
        require_rollback=True,
    )


def envelope() -> EvolutionEnvelope:
    return EvolutionEnvelope(
        capability_id="APB-CAP-0004",
        generation=0,
        maturity_score=0.526,
        uncertainty_score=0.825,
        mutation_floor=0.02,
        mutation_ceiling=0.20,
        effective_mutation_budget=0.072962,
        confidence_floor=0.93,
        occurrence_floor=3,
        max_effective_risk=RiskClass.LOW,
        required_evidence_depth=3,
        regression_tolerances={
            "semantic_equivalence": 0.0,
            "failure_count": 0.0,
            "authority_scope": 0.0,
            "rollback_readiness": 0.0,
        },
        promotion_delta_min=0.05,
        branch_delta_min=0.10,
        niche_occurrence_min=3,
        niche_duration_days_min=14.0,
        niche_replication_min=2,
    )


def real_host_concurrency_candidate(*, deterministic_status: str | None) -> CandidateEvidence:
    """Fixture derived from APB-EXP-0002 live Base44 evidence.

    The experiment contains ten paired trials, semantic equivalence in all trials,
    zero failures, 65.2986% mean wall reduction, LOW experiment risk, rollback,
    and 0.98 confidence. It is still only one independently validated experiment.
    """

    return CandidateEvidence(
        candidate_id="APB-EXP-0002:concurrency-4",
        risk_class=RiskClass.LOW,
        confidence=0.98,
        occurrence_count=10,
        evidence_depth=1,
        rollback_defined=True,
        deterministic_status=deterministic_status,
        protected_deltas={
            "semantic_equivalence": 0.0,
            "failure_count": 0.0,
            "authority_scope": 0.0,
            "rollback_readiness": 0.0,
        },
        current_fit_deltas={"wall_reduction_fraction": 0.6529861601078487},
        current_fit_weights={"wall_reduction_fraction": 1.0},
    )


def test_live_capability_maturity_seed_is_reproducible() -> None:
    inputs = MaturityInputs(
        validation_stability=0.70,
        confidence=0.99,
        rollback_readiness=1.0,
        environment_coverage=0.25,
        repeated_success=0.25,
        promotion_closure=0.25,
        generalization=0.0,
    )
    maturity = maturity_score(inputs)
    uncertainty = uncertainty_score(inputs)

    assert maturity == 0.526
    assert uncertainty == 0.825
    assert mutation_budget(
        mutation_floor=0.02,
        mutation_ceiling=0.20,
        maturity=maturity,
        uncertainty=uncertainty,
    ) == 0.072962


def test_derived_envelope_may_tighten_but_not_loosen_meta_policy() -> None:
    current = envelope()
    assert current.respects(policy())

    loosened = EvolutionEnvelope(
        **{
            **current.__dict__,
            "confidence_floor": 0.80,
            "occurrence_floor": 1,
            "max_effective_risk": RiskClass.MEDIUM,
        }
    )
    assert not loosened.respects(policy())


def test_real_candidate_is_blocked_when_deterministic_validation_is_missing() -> None:
    decision = AdaptiveEvolutionGovernor().decide(
        real_host_concurrency_candidate(deterministic_status=None),
        envelope(),
        policy(),
    )

    assert decision.disposition is EvolutionDisposition.HOLD
    assert decision.gate.disposition is GateDisposition.BLOCKED_PENDING_VALIDATION
    assert decision.compatible is None
    assert decision.current_fit is None


def test_real_candidate_still_needs_independent_evidence_depth_after_pass() -> None:
    decision = AdaptiveEvolutionGovernor().decide(
        real_host_concurrency_candidate(deterministic_status="PASS"),
        envelope(),
        policy(),
    )

    assert decision.disposition is EvolutionDisposition.HOLD
    assert decision.gate.disposition is GateDisposition.BLOCKED_INSUFFICIENT_EVIDENCE
    assert "evidence depth" in decision.gate.reasons[0]


def qualified_candidate(*, semantic_delta: float = 0.0) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id="fixture-qualified",
        risk_class=RiskClass.LOW,
        confidence=0.98,
        occurrence_count=4,
        evidence_depth=3,
        rollback_defined=True,
        deterministic_status="PASS",
        protected_deltas={
            "semantic_equivalence": semantic_delta,
            "failure_count": 0.0,
            "authority_scope": 0.0,
            "rollback_readiness": 0.0,
        },
        current_fit_deltas={"gain": 0.08},
        current_fit_weights={"gain": 1.0},
    )


def test_qualified_compatible_candidate_reaches_promotion_branch() -> None:
    decision = AdaptiveEvolutionGovernor().decide(qualified_candidate(), envelope(), policy())
    assert decision.disposition is EvolutionDisposition.PROMOTION_CANDIDATE
    assert decision.compatible is True


def test_persistent_compatible_niche_can_become_polymorph() -> None:
    candidate = CandidateEvidence(
        **{
            **qualified_candidate().__dict__,
            "current_fit_deltas": {"gain": 0.01},
        }
    )
    niche = NicheEvidence(
        occurrences=4,
        duration_days=21,
        replications=3,
        median_advantage=0.20,
        fit_score=0.20,
        low_switching_cost=True,
    )
    decision = AdaptiveEvolutionGovernor().decide(candidate, envelope(), policy(), niche)
    assert decision.disposition is EvolutionDisposition.POLYMORPH_CANDIDATE


def test_persistent_useful_incompatible_niche_can_trigger_speciation() -> None:
    candidate = CandidateEvidence(
        **{
            **qualified_candidate(semantic_delta=-0.02).__dict__,
            "current_fit_deltas": {"gain": 0.01},
        }
    )
    niche = NicheEvidence(
        occurrences=4,
        duration_days=21,
        replications=3,
        median_advantage=0.20,
        fit_score=0.20,
        low_switching_cost=False,
    )
    decision = AdaptiveEvolutionGovernor().decide(candidate, envelope(), policy(), niche)
    assert decision.disposition is EvolutionDisposition.SPECIATION_CANDIDATE
    assert decision.compatible is False
