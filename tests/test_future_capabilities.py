from frost_core import (
    AttentionAction,
    BranchOption,
    CapabilityStatus,
    CognitionRoute,
    CognitionTask,
    DelegatedCognitionRouter,
    EvidenceClass,
    EvidenceItem,
    IntelligenceAwareness,
    PredictiveAttentionManager,
    Signal,
    StrategicBranchForecaster,
    default_registry,
)


def test_intelligence_awareness_separates_supported_from_unknown() -> None:
    awareness = IntelligenceAwareness()
    supported = awareness.assess(
        [
            EvidenceItem("device returned evidence", EvidenceClass.OBSERVED, 1.0, 0.95),
            EvidenceItem("hash verified", EvidenceClass.DERIVED, 1.0, 0.90),
        ]
    )
    unknown = awareness.assess(
        [EvidenceItem("cause is unknown", EvidenceClass.UNKNOWN, 0.0, 0.0)]
    )

    assert supported.state == "SUPPORTED"
    assert supported.trust_score > 0.75
    assert unknown.state == "UNKNOWN"
    assert unknown.trust_score == 0.0
    assert unknown.uncertainty == 1.0


def test_contradictions_force_contested_state() -> None:
    report = IntelligenceAwareness().assess(
        [
            EvidenceItem("worker passed", EvidenceClass.OBSERVED, 1.0, 1.0),
            EvidenceItem(
                "worker failed",
                EvidenceClass.OBSERVED,
                1.0,
                1.0,
                contradiction=True,
            ),
        ]
    )
    assert report.state == "CONTESTED"
    assert report.trust_score < report.support


def test_predictive_attention_suppresses_low_value_noise() -> None:
    manager = PredictiveAttentionManager()
    decision = manager.decide(
        Signal(
            "noise",
            urgency=0.05,
            impact=0.05,
            confidence=0.90,
            novelty=0.10,
            reversibility=1.0,
            interruption_cost=0.90,
        )
    )
    assert decision.action == AttentionAction.SUPPRESS


def test_predictive_attention_interrupts_urgent_irreversible_signal() -> None:
    manager = PredictiveAttentionManager()
    decision = manager.decide(
        Signal(
            "deadline",
            urgency=0.95,
            impact=0.90,
            confidence=0.90,
            novelty=0.30,
            reversibility=0.10,
            interruption_cost=0.20,
            deadline_hours=1.0,
        )
    )
    assert decision.action == AttentionAction.INTERRUPT


def test_high_impact_low_confidence_requests_evidence_first() -> None:
    decision = PredictiveAttentionManager().decide(
        Signal(
            "uncertain-alert",
            urgency=0.80,
            impact=0.90,
            confidence=0.20,
            novelty=0.80,
            reversibility=0.20,
            interruption_cost=0.10,
            deadline_hours=2.0,
        )
    )
    assert decision.action == AttentionAction.REQUEST_EVIDENCE


def test_delegated_cognition_never_routes_unauthorized_task_to_agent() -> None:
    route = DelegatedCognitionRouter().route(
        CognitionTask(
            "unauthorized",
            risk=0.10,
            ambiguity=0.10,
            reversibility=1.0,
            evidence_coverage=1.0,
            time_sensitivity=0.20,
            authorized=False,
        )
    )
    assert route == CognitionRoute.HUMAN_REVIEW


def test_delegated_cognition_routes_low_risk_authorized_work() -> None:
    route = DelegatedCognitionRouter().route(
        CognitionTask(
            "bounded",
            risk=0.10,
            ambiguity=0.10,
            reversibility=0.95,
            evidence_coverage=0.90,
            time_sensitivity=0.20,
            authorized=True,
        )
    )
    assert route == CognitionRoute.BOUNDED_AGENT


def test_strategic_forecaster_preserves_high_optionality_branch() -> None:
    forecaster = StrategicBranchForecaster()
    fixed = BranchOption("fixed", 0.90, 0.80, 0.20, 0.15, 0.20, 0.05, 0.05)
    adaptable = BranchOption("adaptable", 0.75, 0.70, 0.20, 0.15, 0.15, 0.40, 0.95)
    ranked = forecaster.rank([fixed, adaptable])
    assert ranked[0].branch_id == "adaptable"


def test_registry_enables_safe_future_capabilities_but_keeps_hard_gates() -> None:
    registry = default_registry()
    enabled_ids = {item.capability_id for item in registry.enabled()}

    assert "intelligence_awareness" in enabled_ids
    assert "predictive_attention" in enabled_ids
    assert "delegated_cognition" in enabled_ids
    assert "strategic_branch_forecasting" in enabled_ids
    assert registry.get("adversarial_candidate_execution").status == CapabilityStatus.GATED
    assert registry.get("physical_device_autonomy").status == CapabilityStatus.GATED
    assert registry.get("autonomous_main_promotion").status == CapabilityStatus.DISABLED


def test_enabled_capability_still_requires_prerequisites() -> None:
    registry = default_registry()
    assert not registry.can_execute("intelligence_awareness", [])
    assert registry.can_execute("intelligence_awareness", ["evidence_input"])
