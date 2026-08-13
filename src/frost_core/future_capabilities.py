from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import exp
from typing import Iterable


class EvidenceClass(StrEnum):
    OBSERVED = "OBSERVED"
    EXPLICIT = "EXPLICIT"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    SPECULATIVE = "SPECULATIVE"
    UNKNOWN = "UNKNOWN"


_EVIDENCE_WEIGHT = {
    EvidenceClass.OBSERVED: 1.0,
    EvidenceClass.EXPLICIT: 0.95,
    EvidenceClass.DERIVED: 0.85,
    EvidenceClass.INFERRED: 0.55,
    EvidenceClass.SPECULATIVE: 0.25,
    EvidenceClass.UNKNOWN: 0.0,
}


@dataclass(frozen=True)
class EvidenceItem:
    proposition: str
    evidence_class: EvidenceClass
    support: float
    confidence: float
    contradiction: bool = False

    def __post_init__(self) -> None:
        for name, value in (("support", self.support), ("confidence", self.confidence)):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if not self.proposition.strip():
            raise ValueError("proposition must not be empty")


@dataclass(frozen=True)
class AwarenessReport:
    support: float
    uncertainty: float
    contradiction_pressure: float
    evidence_coverage: float
    trust_score: float
    state: str


class IntelligenceAwareness:
    """Operational epistemic awareness; not a claim of consciousness."""

    def assess(self, evidence: Iterable[EvidenceItem]) -> AwarenessReport:
        items = tuple(evidence)
        if not items:
            return AwarenessReport(0.0, 1.0, 0.0, 0.0, 0.0, "UNKNOWN")

        weighted_support = 0.0
        available_weight = 0.0
        contradiction_pressure = 0.0
        known_count = 0

        for item in items:
            class_weight = _EVIDENCE_WEIGHT[item.evidence_class]
            effective_weight = class_weight * item.confidence
            weighted_support += item.support * effective_weight
            available_weight += effective_weight
            if item.evidence_class is not EvidenceClass.UNKNOWN:
                known_count += 1
            if item.contradiction:
                contradiction_pressure += max(0.25, effective_weight)

        support = weighted_support / available_weight if available_weight else 0.0
        coverage = known_count / len(items)
        contradiction = min(1.0, contradiction_pressure / len(items))
        uncertainty = min(1.0, 1.0 - (support * coverage) + 0.5 * contradiction)
        trust = max(0.0, support * coverage * (1.0 - contradiction))

        if contradiction >= 0.25:
            state = "CONTESTED"
        elif trust >= 0.75:
            state = "SUPPORTED"
        elif coverage == 0.0:
            state = "UNKNOWN"
        else:
            state = "INCOMPLETE"

        return AwarenessReport(
            support=round(support, 6),
            uncertainty=round(uncertainty, 6),
            contradiction_pressure=round(contradiction, 6),
            evidence_coverage=round(coverage, 6),
            trust_score=round(trust, 6),
            state=state,
        )


class AttentionAction(StrEnum):
    INTERRUPT = "INTERRUPT"
    QUEUE = "QUEUE"
    DELEGATE = "DELEGATE"
    SUPPRESS = "SUPPRESS"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"


@dataclass(frozen=True)
class Signal:
    signal_id: str
    urgency: float
    impact: float
    confidence: float
    novelty: float
    reversibility: float
    interruption_cost: float
    deadline_hours: float | None = None
    delegable: bool = True

    def __post_init__(self) -> None:
        bounded = (
            ("urgency", self.urgency),
            ("impact", self.impact),
            ("confidence", self.confidence),
            ("novelty", self.novelty),
            ("reversibility", self.reversibility),
            ("interruption_cost", self.interruption_cost),
        )
        for name, value in bounded:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.deadline_hours is not None and self.deadline_hours < 0:
            raise ValueError("deadline_hours must be non-negative")


@dataclass(frozen=True)
class AttentionDecision:
    signal_id: str
    score: float
    action: AttentionAction
    reason: str


class PredictiveAttentionManager:
    """Prioritize future consequences instead of emitting raw notification volume."""

    def score(self, signal: Signal) -> float:
        deadline_pressure = 0.0
        if signal.deadline_hours is not None:
            deadline_pressure = exp(-signal.deadline_hours / 12.0)

        irreversibility = 1.0 - signal.reversibility
        value = (
            0.28 * signal.urgency
            + 0.28 * signal.impact
            + 0.14 * signal.confidence
            + 0.08 * signal.novelty
            + 0.12 * irreversibility
            + 0.10 * deadline_pressure
            - 0.18 * signal.interruption_cost
        )
        return max(0.0, min(1.0, value))

    def decide(self, signal: Signal) -> AttentionDecision:
        score = self.score(signal)
        irreversibility = 1.0 - signal.reversibility

        if signal.confidence < 0.30 and signal.impact >= 0.60:
            action = AttentionAction.REQUEST_EVIDENCE
            reason = "high-impact signal lacks enough confidence for action"
        elif score >= 0.70 or (signal.urgency >= 0.85 and irreversibility >= 0.70):
            action = AttentionAction.INTERRUPT
            reason = "expected consequence exceeds interruption threshold"
        elif score >= 0.45 and signal.delegable:
            action = AttentionAction.DELEGATE
            reason = "material signal can be handled without human interruption"
        elif score >= 0.28:
            action = AttentionAction.QUEUE
            reason = "signal matters, but immediate interruption is not justified"
        else:
            action = AttentionAction.SUPPRESS
            reason = "expected value does not justify attention cost"

        return AttentionDecision(signal.signal_id, round(score, 6), action, reason)


class CognitionRoute(StrEnum):
    BOUNDED_AGENT = "BOUNDED_AGENT"
    MULTI_AGENT_REVIEW = "MULTI_AGENT_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    DEFER = "DEFER"


@dataclass(frozen=True)
class CognitionTask:
    task_id: str
    risk: float
    ambiguity: float
    reversibility: float
    evidence_coverage: float
    time_sensitivity: float
    authorized: bool

    def __post_init__(self) -> None:
        for name, value in (
            ("risk", self.risk),
            ("ambiguity", self.ambiguity),
            ("reversibility", self.reversibility),
            ("evidence_coverage", self.evidence_coverage),
            ("time_sensitivity", self.time_sensitivity),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


class DelegatedCognitionRouter:
    """Choose the least-human-attention route that preserves control boundaries."""

    def route(self, task: CognitionTask) -> CognitionRoute:
        if not task.authorized:
            return CognitionRoute.HUMAN_REVIEW

        irreversibility = 1.0 - task.reversibility
        if task.risk >= 0.70 or irreversibility >= 0.75:
            return CognitionRoute.HUMAN_REVIEW
        if task.evidence_coverage < 0.35 and task.ambiguity >= 0.60:
            return CognitionRoute.DEFER
        if task.risk >= 0.40 or task.ambiguity >= 0.45:
            return CognitionRoute.MULTI_AGENT_REVIEW
        return CognitionRoute.BOUNDED_AGENT


class CapabilityStatus(StrEnum):
    ENABLED_EXPERIMENTAL = "ENABLED_EXPERIMENTAL"
    GATED = "GATED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class CapabilityActivation:
    capability_id: str
    status: CapabilityStatus
    reason: str
    requires: tuple[str, ...] = field(default_factory=tuple)


class CapabilityRegistry:
    def __init__(self, capabilities: Iterable[CapabilityActivation]) -> None:
        values = tuple(capabilities)
        if len({item.capability_id for item in values}) != len(values):
            raise ValueError("duplicate capability_id")
        self._capabilities = {item.capability_id: item for item in values}

    def get(self, capability_id: str) -> CapabilityActivation:
        return self._capabilities[capability_id]

    def enabled(self) -> tuple[CapabilityActivation, ...]:
        return tuple(
            item
            for item in self._capabilities.values()
            if item.status is CapabilityStatus.ENABLED_EXPERIMENTAL
        )

    def can_execute(self, capability_id: str, satisfied_requirements: Iterable[str]) -> bool:
        item = self.get(capability_id)
        if item.status is not CapabilityStatus.ENABLED_EXPERIMENTAL:
            return False
        satisfied = set(satisfied_requirements)
        return set(item.requires).issubset(satisfied)


def default_registry() -> CapabilityRegistry:
    return CapabilityRegistry(
        (
            CapabilityActivation(
                "intelligence_awareness",
                CapabilityStatus.ENABLED_EXPERIMENTAL,
                "host-safe epistemic state calculation",
                ("evidence_input",),
            ),
            CapabilityActivation(
                "predictive_attention",
                CapabilityStatus.ENABLED_EXPERIMENTAL,
                "host-safe attention scoring and suppression",
                ("signal_input",),
            ),
            CapabilityActivation(
                "delegated_cognition",
                CapabilityStatus.ENABLED_EXPERIMENTAL,
                "bounded routing only; does not grant execution authority",
                ("authorization_state", "task_risk"),
            ),
            CapabilityActivation(
                "strategic_branch_forecasting",
                CapabilityStatus.ENABLED_EXPERIMENTAL,
                "forecast metadata can guide experiments but cannot self-promote",
                ("bounded_candidates", "locked_evaluator"),
            ),
            CapabilityActivation(
                "adversarial_candidate_execution",
                CapabilityStatus.GATED,
                "requires issue #18 hard sandbox before execution",
                ("hard_sandbox", "network_default_deny", "secret_isolation"),
            ),
            CapabilityActivation(
                "autonomous_main_promotion",
                CapabilityStatus.DISABLED,
                "explicit human promotion remains a canonical control boundary",
            ),
            CapabilityActivation(
                "physical_device_autonomy",
                CapabilityStatus.GATED,
                "requires empirical Android/Termux validation and bounded worker evidence",
                ("device_validated", "persistent_validated", "audit_verified"),
            ),
        )
    )
