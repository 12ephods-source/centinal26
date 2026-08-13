from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from frost_core import (
    BranchOption,
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

from .core import Engine, Verification
from .evolution_kernel import (
    CandidateGovernanceEvidence,
    EvolutionKernelPolicy,
    MetaPolicyConstraints,
    PersistenceEvidence,
    RiskClass,
    compute_envelope,
    govern_candidate,
)

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


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return value


def _float_mapping(value: object, name: str) -> dict[str, float]:
    raw = _mapping(value, name)
    return {str(key): float(item) for key, item in raw.items()}


def _meta_policy(raw: dict[str, Any]) -> MetaPolicyConstraints:
    return MetaPolicyConstraints(
        min_occurrences=int(raw["min_occurrences"]),
        min_confidence=float(raw["min_confidence"]),
        max_auto_risk=RiskClass(raw["max_auto_risk"]),
        require_deterministic_pass=bool(raw["require_deterministic_pass"]),
        require_rollback=bool(raw["require_rollback"]),
        allow_schema_mutation=bool(raw["allow_schema_mutation"]),
        allow_external_side_effects=bool(raw["allow_external_side_effects"]),
    )


def _kernel_policy(raw: dict[str, Any]) -> EvolutionKernelPolicy:
    return EvolutionKernelPolicy(
        maturity_weights=_float_mapping(raw["maturity_weights"], "maturity_weights"),
        uncertainty_weights=_float_mapping(
            raw["uncertainty_weights"],
            "uncertainty_weights",
        ),
        mutation_floor=float(raw["mutation_floor"]),
        mutation_ceiling=float(raw["mutation_ceiling"]),
        annealing_rate=float(raw["annealing_rate"]),
        exploration_floor_fraction=float(raw["exploration_floor_fraction"]),
        confidence_floor=float(raw["confidence_floor"]),
        occurrence_floor=int(raw["occurrence_floor"]),
        required_evidence_depth=int(raw["required_evidence_depth"]),
        regression_tolerances=_float_mapping(
            raw["regression_tolerances"],
            "regression_tolerances",
        ),
        promotion_delta_min=float(raw["promotion_delta_min"]),
        branch_delta_min=float(raw["branch_delta_min"]),
        niche_occurrence_min=int(raw["niche_occurrence_min"]),
        niche_duration_min_days=float(raw["niche_duration_min_days"]),
        niche_replication_min=int(raw["niche_replication_min"]),
        max_effective_risk=RiskClass(raw["max_effective_risk"]),
    )


def _candidate(raw: dict[str, Any]) -> CandidateGovernanceEvidence:
    persistence = _mapping(raw["persistence"], "candidate.persistence")
    deterministic = raw.get("deterministic_status")
    return CandidateGovernanceEvidence(
        candidate_id=str(raw["candidate_id"]),
        authorized=bool(raw["authorized"]),
        risk_class=RiskClass(raw["risk_class"]),
        confidence=float(raw["confidence"]),
        occurrence_count=int(raw["occurrence_count"]),
        evidence_depth=int(raw["evidence_depth"]),
        rollback_defined=bool(raw["rollback_defined"]),
        deterministic_status=None if deterministic is None else str(deterministic),
        schema_mutation=bool(raw.get("schema_mutation", False)),
        external_side_effects=bool(raw.get("external_side_effects", False)),
        protected_deltas=_float_mapping(raw["protected_deltas"], "protected_deltas"),
        current_fit_deltas=_float_mapping(raw["current_fit_deltas"], "current_fit_deltas"),
        current_fit_weights=_float_mapping(
            raw["current_fit_weights"],
            "current_fit_weights",
        ),
        niche_fit_deltas=_float_mapping(raw["niche_fit_deltas"], "niche_fit_deltas"),
        niche_fit_weights=_float_mapping(raw["niche_fit_weights"], "niche_fit_weights"),
        persistence=PersistenceEvidence(
            independent_occurrences=int(persistence["independent_occurrences"]),
            duration_days=float(persistence["duration_days"]),
            independent_replications=int(persistence["independent_replications"]),
            median_advantage=float(persistence["median_advantage"]),
        ),
        low_switching_cost=bool(raw["low_switching_cost"]),
        high_coexistence_cost=bool(raw["high_coexistence_cost"]),
    )


def evolution_evaluate(data: dict[str, Any]) -> dict[str, Any]:
    """Advisory-only Dragon Evolution evaluation through the canonical engine."""
    raw_meta = _mapping(data.get("meta_policy"), "meta_policy")
    raw_policy = _mapping(data.get("kernel_policy"), "kernel_policy")
    raw_seed = _mapping(data.get("seed"), "seed")
    raw_candidate = _mapping(data.get("candidate"), "candidate")

    meta_policy = _meta_policy(raw_meta)
    kernel_policy = _kernel_policy(raw_policy)
    envelope = compute_envelope(
        capability_id=str(raw_seed["capability_id"]),
        generation=int(raw_seed["generation"]),
        maturity_components=_float_mapping(
            raw_seed["maturity_components"],
            "maturity_components",
        ),
        uncertainty_components=_float_mapping(
            raw_seed["uncertainty_components"],
            "uncertainty_components",
        ),
        policy=kernel_policy,
        meta_policy=meta_policy,
        source_meta_policy=str(raw_seed["source_meta_policy"]),
        source_policy_hash=str(raw_seed["source_policy_hash"]),
        source_evidence_hash=str(raw_seed["source_evidence_hash"]),
    )
    result = govern_candidate(_candidate(raw_candidate), envelope, meta_policy)
    return {
        "envelope": envelope.to_dict(),
        "decision": asdict(result),
        "promotion_authority": False,
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
