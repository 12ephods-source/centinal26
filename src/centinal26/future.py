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
        ("system.future_capabilities", capability_status),
    )
    for name, executor in capabilities:
        runtime.register(name, executor, exact_verifier(executor))
