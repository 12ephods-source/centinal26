from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class RiskClass(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_RISK_RANK = {RiskClass.LOW: 0, RiskClass.MEDIUM: 1, RiskClass.HIGH: 2}


class GateDisposition(StrEnum):
    PASS = "PASS"
    BLOCKED_PENDING_VALIDATION = "BLOCKED_PENDING_VALIDATION"
    BLOCKED_INSUFFICIENT_EVIDENCE = "BLOCKED_INSUFFICIENT_EVIDENCE"
    BLOCKED_ROLLBACK_REQUIRED = "BLOCKED_ROLLBACK_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    REJECT_VALIDATION_FAILED = "REJECT_VALIDATION_FAILED"


class EvolutionDisposition(StrEnum):
    REJECT = "REJECT"
    HOLD = "HOLD"
    PROMOTION_CANDIDATE = "PROMOTION_CANDIDATE"
    POLYMORPH_CANDIDATE = "POLYMORPH_CANDIDATE"
    SPECIATION_CANDIDATE = "SPECIATION_CANDIDATE"


@dataclass(frozen=True)
class MaturityInputs:
    """Evidence-derived maturity components, each normalized to [0, 1]."""

    validation_stability: float
    confidence: float
    rollback_readiness: float
    environment_coverage: float
    repeated_success: float
    promotion_closure: float
    generalization: float

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


def maturity_score(inputs: MaturityInputs) -> float:
    """Conservative capability-specific maturity M(c,t).

    Generalization is weighted heavily enough that a capability cannot appear
    mature merely because one host experiment is successful.
    """

    score = (
        0.20 * inputs.validation_stability
        + 0.15 * inputs.confidence
        + 0.15 * inputs.rollback_readiness
        + 0.15 * inputs.environment_coverage
        + 0.10 * inputs.repeated_success
        + 0.10 * inputs.promotion_closure
        + 0.15 * inputs.generalization
    )
    return round(score, 6)


def uncertainty_score(inputs: MaturityInputs) -> float:
    """Unresolved opportunity/uncertainty U(c,t), emphasizing coverage gaps."""

    score = (
        0.40 * (1.0 - inputs.environment_coverage)
        + 0.30 * (1.0 - inputs.generalization)
        + 0.20 * (1.0 - inputs.repeated_success)
        + 0.10 * (1.0 - inputs.promotion_closure)
    )
    return round(score, 6)


def mutation_budget(
    *,
    mutation_floor: float,
    mutation_ceiling: float,
    maturity: float,
    uncertainty: float,
    annealing_rate: float = 2.0,
    exploration_floor_fraction: float = 0.10,
) -> float:
    """Capability-specific differential plasticity μ(c,t)."""

    if mutation_floor < 0 or mutation_ceiling < mutation_floor:
        raise ValueError("invalid mutation bounds")
    for name, value in (("maturity", maturity), ("uncertainty", uncertainty)):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]")
    if annealing_rate < 0:
        raise ValueError("annealing_rate must be non-negative")
    if not 0.0 <= exploration_floor_fraction <= 1.0:
        raise ValueError("exploration_floor_fraction must be in [0, 1]")

    uncertainty_factor = exploration_floor_fraction + (
        (1.0 - exploration_floor_fraction) * uncertainty
    )
    budget = mutation_floor + (
        (mutation_ceiling - mutation_floor)
        * math.exp(-annealing_rate * maturity)
        * uncertainty_factor
    )
    return round(max(mutation_floor, min(mutation_ceiling, budget)), 6)


@dataclass(frozen=True)
class MetaPolicy:
    min_occurrences: int
    min_confidence: float
    max_auto_risk: RiskClass
    require_deterministic_pass: bool
    require_rollback: bool


@dataclass(frozen=True)
class EvolutionEnvelope:
    capability_id: str
    generation: int
    maturity_score: float
    uncertainty_score: float
    mutation_floor: float
    mutation_ceiling: float
    effective_mutation_budget: float
    confidence_floor: float
    occurrence_floor: int
    max_effective_risk: RiskClass
    required_evidence_depth: int
    regression_tolerances: Mapping[str, float]
    promotion_delta_min: float
    branch_delta_min: float
    niche_occurrence_min: int
    niche_duration_days_min: float
    niche_replication_min: int

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        for name, value in (
            ("maturity_score", self.maturity_score),
            ("uncertainty_score", self.uncertainty_score),
            ("confidence_floor", self.confidence_floor),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.occurrence_floor < 1 or self.required_evidence_depth < 1:
            raise ValueError("evidence floors must be positive")

    def respects(self, policy: MetaPolicy) -> bool:
        """A derived envelope may tighten but never loosen MetaPolicy."""

        return (
            self.confidence_floor >= policy.min_confidence
            and self.occurrence_floor >= policy.min_occurrences
            and _RISK_RANK[self.max_effective_risk] <= _RISK_RANK[policy.max_auto_risk]
        )


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    risk_class: RiskClass
    confidence: float
    occurrence_count: int
    evidence_depth: int
    rollback_defined: bool
    deterministic_status: str | None
    protected_deltas: Mapping[str, float]
    current_fit_deltas: Mapping[str, float]
    current_fit_weights: Mapping[str, float]

    def current_fit(self) -> float:
        missing = set(self.current_fit_weights) - set(self.current_fit_deltas)
        if missing:
            raise ValueError(f"missing fit deltas: {sorted(missing)}")
        return round(
            sum(
                self.current_fit_weights[name] * self.current_fit_deltas[name]
                for name in self.current_fit_weights
            ),
            6,
        )


@dataclass(frozen=True)
class NicheEvidence:
    occurrences: int
    duration_days: float
    replications: int
    median_advantage: float
    fit_score: float
    low_switching_cost: bool


@dataclass(frozen=True)
class GateResult:
    disposition: GateDisposition
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EvolutionDecision:
    disposition: EvolutionDisposition
    compatible: bool | None
    current_fit: float | None
    niche_persistent: bool | None
    gate: GateResult
    reasons: tuple[str, ...]


class AdaptiveEvolutionGovernor:
    """Policy-subordinate governor for bounded capability evolution."""

    def constitutional_gate(
        self,
        candidate: CandidateEvidence,
        envelope: EvolutionEnvelope,
        policy: MetaPolicy,
    ) -> GateResult:
        if not envelope.respects(policy):
            raise ValueError("evolution envelope loosens its source MetaPolicy")

        if candidate.deterministic_status == "FAIL":
            return GateResult(
                GateDisposition.REJECT_VALIDATION_FAILED,
                ("deterministic validation explicitly failed",),
            )
        if policy.require_deterministic_pass and candidate.deterministic_status != "PASS":
            return GateResult(
                GateDisposition.BLOCKED_PENDING_VALIDATION,
                ("MetaPolicy requires an explicit deterministic PASS",),
            )
        if policy.require_rollback and not candidate.rollback_defined:
            return GateResult(
                GateDisposition.BLOCKED_ROLLBACK_REQUIRED,
                ("MetaPolicy requires a defined rollback",),
            )
        if candidate.confidence < envelope.confidence_floor:
            return GateResult(
                GateDisposition.BLOCKED_INSUFFICIENT_EVIDENCE,
                ("candidate confidence is below the derived envelope floor",),
            )
        if candidate.occurrence_count < envelope.occurrence_floor:
            return GateResult(
                GateDisposition.BLOCKED_INSUFFICIENT_EVIDENCE,
                ("independent occurrence count is below the derived floor",),
            )
        if candidate.evidence_depth < envelope.required_evidence_depth:
            return GateResult(
                GateDisposition.BLOCKED_INSUFFICIENT_EVIDENCE,
                ("validated evidence depth is below the derived floor",),
            )
        if _RISK_RANK[candidate.risk_class] > _RISK_RANK[envelope.max_effective_risk]:
            return GateResult(
                GateDisposition.HUMAN_REVIEW_REQUIRED,
                ("candidate risk exceeds autonomous envelope",),
            )
        return GateResult(GateDisposition.PASS, ())

    def compatible(self, candidate: CandidateEvidence, envelope: EvolutionEnvelope) -> bool:
        missing = set(envelope.regression_tolerances) - set(candidate.protected_deltas)
        if missing:
            raise ValueError(f"missing protected deltas: {sorted(missing)}")
        return all(
            candidate.protected_deltas[metric] >= -tolerance
            for metric, tolerance in envelope.regression_tolerances.items()
        )

    def persistent_niche(
        self,
        niche: NicheEvidence,
        envelope: EvolutionEnvelope,
    ) -> bool:
        return (
            niche.occurrences >= envelope.niche_occurrence_min
            and niche.duration_days >= envelope.niche_duration_days_min
            and niche.replications >= envelope.niche_replication_min
            and niche.median_advantage >= envelope.branch_delta_min
        )

    def decide(
        self,
        candidate: CandidateEvidence,
        envelope: EvolutionEnvelope,
        policy: MetaPolicy,
        niche: NicheEvidence | None = None,
    ) -> EvolutionDecision:
        gate = self.constitutional_gate(candidate, envelope, policy)
        if gate.disposition is GateDisposition.REJECT_VALIDATION_FAILED:
            return EvolutionDecision(
                EvolutionDisposition.REJECT,
                None,
                None,
                None,
                gate,
                gate.reasons,
            )
        if gate.disposition is not GateDisposition.PASS:
            return EvolutionDecision(
                EvolutionDisposition.HOLD,
                None,
                None,
                None,
                gate,
                gate.reasons,
            )

        compatible = self.compatible(candidate, envelope)
        current_fit = candidate.current_fit()
        niche_persistent = None if niche is None else self.persistent_niche(niche, envelope)

        if compatible and current_fit >= envelope.promotion_delta_min:
            return EvolutionDecision(
                EvolutionDisposition.PROMOTION_CANDIDATE,
                True,
                current_fit,
                niche_persistent,
                gate,
                ("validated compatible improvement exceeds promotion threshold",),
            )

        if niche is not None and niche_persistent and niche.fit_score >= envelope.branch_delta_min:
            if compatible and niche.low_switching_cost:
                return EvolutionDecision(
                    EvolutionDisposition.POLYMORPH_CANDIDATE,
                    True,
                    current_fit,
                    True,
                    gate,
                    ("persistent niche advantage is compatible and cheaply selectable",),
                )
            if not compatible:
                return EvolutionDecision(
                    EvolutionDisposition.SPECIATION_CANDIDATE,
                    False,
                    current_fit,
                    True,
                    gate,
                    ("persistent niche advantage is useful but incompatible with parent form",),
                )

        return EvolutionDecision(
            EvolutionDisposition.HOLD,
            compatible,
            current_fit,
            niche_persistent,
            gate,
            ("candidate has not cleared promotion, polymorphism, or speciation thresholds",),
        )
