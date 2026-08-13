from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from frost_core import (
    AdaptiveEvolutionGovernor,
    BranchOption,
    CandidateEvidence,
    CognitionTask,
    DelegatedCognitionRouter,
    EvidenceClass,
    EvidenceItem,
    EvolutionEnvelope,
    IntelligenceAwareness,
    MetaPolicy,
    NicheEvidence,
    PredictiveAttentionManager,
    RiskClass,
    Signal,
    StrategicBranchForecaster,
    default_registry,
)

from .core import Engine, Verification

Executor = Callable[[dict[str, Any]], dict[str, Any]]


def intelligence_awareness(data: dict[str, Any]) -> dict[str, Any]:
    raw_evidence = data.get("evidence")
    if not isinstance(raw_evidence, list):
        raise TypeError("evidence must be a list")
    evidence = [
        EvidenceItem(
            proposition=str(item["proposition"]),
            evidence_class=EvidenceClass(item["evidence_class"]),
            support=float(item["support"]),
            confidence=float(item["confidence"]),
            contradiction=bool(item.get("contradiction", False)),
        )
        for item in raw_evidence
    ]
    return asdict(IntelligenceAwareness().assess(evidence))


def predictive_attention(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("signal")
    if not isinstance(raw, dict):
        raise TypeError("signal must be an object")
    decision = PredictiveAttentionManager().decide(
        Signal(
            signal_id=str(raw["signal_id"]),
            urgency=float(raw["urgency"]),
            impact=float(raw["impact"]),
            confidence=float(raw["confidence"]),
            novelty=float(raw["novelty"]),
            reversibility=float(raw["reversibility"]),
            interruption_cost=float(raw["interruption_cost"]),
            deadline_hours=(
                None if raw.get("deadline_hours") is None else float(raw["deadline_hours"])
            ),
            delegable=bool(raw.get("delegable", True)),
        )
    )
    return asdict(decision)


def delegated_cognition(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("task")
    if not isinstance(raw, dict):
        raise TypeError("task must be an object")
    task = CognitionTask(
        task_id=str(raw["task_id"]),
        risk=float(raw["risk"]),
        ambiguity=float(raw["ambiguity"]),
        reversibility=float(raw["reversibility"]),
        evidence_coverage=float(raw["evidence_coverage"]),
        time_sensitivity=float(raw["time_sensitivity"]),
        authorized=bool(raw["authorized"]),
    )
    return {"task_id": task.task_id, "route": DelegatedCognitionRouter().route(task)}


def strategic_forecast(data: dict[str, Any]) -> dict[str, Any]:
    raw_options = data.get("options")
    if not isinstance(raw_options, list):
        raise TypeError("options must be a list")
    if not raw_options:
        raise ValueError("options must not be empty")
    options = [
        BranchOption(
            branch_id=str(item["branch_id"]),
            success_probability=float(item["success_probability"]),
            expected_gain=float(item["expected_gain"]),
            cost=float(item["cost"]),
            risk=float(item["risk"]),
            irreversibility=float(item["irreversibility"]),
            uncertainty=float(item["uncertainty"]),
            future_optionality=float(item["future_optionality"]),
        )
        for item in raw_options
    ]
    ranked = StrategicBranchForecaster().rank(options)
    return {"ranked": [asdict(item) for item in ranked], "promotion_authority": False}


def evolution_evaluate(data: dict[str, Any]) -> dict[str, Any]:
    raw_policy = data.get("policy")
    raw_envelope = data.get("envelope")
    raw_candidate = data.get("candidate")
    raw_niche = data.get("niche")
    if not isinstance(raw_policy, dict):
        raise TypeError("policy must be an object")
    if not isinstance(raw_envelope, dict):
        raise TypeError("envelope must be an object")
    if not isinstance(raw_candidate, dict):
        raise TypeError("candidate must be an object")
    if raw_niche is not None and not isinstance(raw_niche, dict):
        raise TypeError("niche must be an object when provided")

    policy = MetaPolicy(
        min_occurrences=int(raw_policy["min_occurrences"]),
        min_confidence=float(raw_policy["min_confidence"]),
        max_auto_risk=RiskClass(raw_policy["max_auto_risk"]),
        require_deterministic_pass=bool(raw_policy["require_deterministic_pass"]),
        require_rollback=bool(raw_policy["require_rollback"]),
        allow_schema_mutation=bool(raw_policy.get("allow_schema_mutation", False)),
        allow_external_side_effects=bool(raw_policy.get("allow_external_side_effects", False)),
    )
    envelope = EvolutionEnvelope(
        capability_id=str(raw_envelope["capability_id"]),
        generation=int(raw_envelope["generation"]),
        maturity_score=float(raw_envelope["maturity_score"]),
        uncertainty_score=float(raw_envelope["uncertainty_score"]),
        mutation_floor=float(raw_envelope["mutation_floor"]),
        mutation_ceiling=float(raw_envelope["mutation_ceiling"]),
        effective_mutation_budget=float(raw_envelope["effective_mutation_budget"]),
        confidence_floor=float(raw_envelope["confidence_floor"]),
        occurrence_floor=int(raw_envelope["occurrence_floor"]),
        max_effective_risk=RiskClass(raw_envelope["max_effective_risk"]),
        required_evidence_depth=int(raw_envelope["required_evidence_depth"]),
        regression_tolerances={
            str(key): float(value)
            for key, value in raw_envelope["regression_tolerances"].items()
        },
        promotion_delta_min=float(raw_envelope["promotion_delta_min"]),
        branch_delta_min=float(raw_envelope["branch_delta_min"]),
        niche_occurrence_min=int(raw_envelope["niche_occurrence_min"]),
        niche_duration_days_min=float(raw_envelope["niche_duration_days_min"]),
        niche_replication_min=int(raw_envelope["niche_replication_min"]),
        source_meta_policy=str(raw_envelope.get("source_meta_policy", "meta-automation-v1")),
        status=str(raw_envelope.get("status", "active")),
    )
    candidate = CandidateEvidence(
        candidate_id=str(raw_candidate["candidate_id"]),
        authorized=bool(raw_candidate["authorized"]),
        risk_class=RiskClass(raw_candidate["risk_class"]),
        confidence=float(raw_candidate["confidence"]),
        occurrence_count=int(raw_candidate["occurrence_count"]),
        evidence_depth=int(raw_candidate["evidence_depth"]),
        rollback_defined=bool(raw_candidate["rollback_defined"]),
        deterministic_status=(
            None
            if raw_candidate.get("deterministic_status") is None
            else str(raw_candidate["deterministic_status"])
        ),
        protected_deltas={
            str(key): float(value) for key, value in raw_candidate["protected_deltas"].items()
        },
        current_fit_deltas={
            str(key): float(value) for key, value in raw_candidate["current_fit_deltas"].items()
        },
        current_fit_weights={
            str(key): float(value) for key, value in raw_candidate["current_fit_weights"].items()
        },
        schema_mutation=bool(raw_candidate.get("schema_mutation", False)),
        external_side_effects=bool(raw_candidate.get("external_side_effects", False)),
    )
    niche = None
    if raw_niche is not None:
        niche = NicheEvidence(
            occurrences=int(raw_niche["occurrences"]),
            duration_days=float(raw_niche["duration_days"]),
            replications=int(raw_niche["replications"]),
            median_advantage=float(raw_niche["median_advantage"]),
            fit_deltas={
                str(key): float(value) for key, value in raw_niche["fit_deltas"].items()
            },
            fit_weights={
                str(key): float(value) for key, value in raw_niche["fit_weights"].items()
            },
            low_switching_cost=bool(raw_niche["low_switching_cost"]),
            high_coexistence_cost=bool(raw_niche["high_coexistence_cost"]),
        )

    decision = AdaptiveEvolutionGovernor().decide(candidate, envelope, policy, niche)
    return {
        "decision": asdict(decision),
        "promotion_authority": False,
        "source_meta_policy": envelope.source_meta_policy,
    }


def capability_status(data: dict[str, Any]) -> dict[str, Any]:
    if data:
        raise ValueError("capability status does not accept input fields")
    registry = default_registry()
    enabled = {item.capability_id for item in registry.enabled()}
    capability_ids = (
        "intelligence_awareness",
        "predictive_attention",
        "delegated_cognition",
        "strategic_branch_forecasting",
        "adversarial_candidate_execution",
        "autonomous_main_promotion",
        "physical_device_autonomy",
    )
    return {
        "capabilities": [asdict(registry.get(capability_id)) for capability_id in capability_ids],
        "enabled": sorted(enabled),
    }


def exact_verifier(executor: Executor) -> Callable[[dict[str, Any], dict[str, Any]], Verification]:
    def verify(data: dict[str, Any], output: dict[str, Any]) -> Verification:
        expected = executor(data)
        return Verification(
            passed=output == expected,
            evidence={"method": "deterministic_recomputation"},
        )

    return verify


def register_future_capabilities(runtime: Engine) -> None:
    capabilities: tuple[tuple[str, Executor], ...] = (
        ("cognition.intelligence_awareness", intelligence_awareness),
        ("cognition.predictive_attention", predictive_attention),
        ("cognition.delegated_route", delegated_cognition),
        ("cognition.strategic_forecast", strategic_forecast),
        ("evolution.evaluate_candidate", evolution_evaluate),
        ("system.future_capabilities", capability_status),
    )
    for name, executor in capabilities:
        runtime.register(name, executor, exact_verifier(executor))
