from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class RiskClass(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_RISK_RANK = {RiskClass.LOW: 0, RiskClass.MEDIUM: 1, RiskClass.HIGH: 2}


class GateDisposition(StrEnum):
    PASS = "PASS"
    BLOCKED_UNAUTHORIZED = "BLOCKED_UNAUTHORIZED"
    BLOCKED_PENDING_VALIDATION = "BLOCKED_PENDING_VALIDATION"
    BLOCKED_INSUFFICIENT_EVIDENCE = "BLOCKED_INSUFFICIENT_EVIDENCE"
    BLOCKED_ROLLBACK_REQUIRED = "BLOCKED_ROLLBACK_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    REJECT_VALIDATION_FAILED = "REJECT_VALIDATION_FAILED"


class EvolutionDisposition(StrEnum):
    REJECT_FROM_PROMOTION = "REJECT_FROM_PROMOTION"
    PROMOTION_CANDIDATE = "PROMOTION_CANDIDATE"
    POLYMORPH_CANDIDATE = "POLYMORPH_CANDIDATE"
    SPECIATION_CANDIDATE = "SPECIATION_CANDIDATE"


@dataclass(frozen=True)
class MaturityInputs:
    """Evidence-derived capability maturity components, normalized to [0, 1]."""

    validation_stability: float
    regression_resilience: float
    environment_coverage: float
    rollback_readiness: float
    repeated_success: float
    promotion_closure: float

    def __post_init__(self) -> None:
        _validate_unit_fields(self.__dict__)


@dataclass(frozen=True)
class UncertaintyInputs:
    """Unresolved uncertainty/opportunity components, normalized to [0, 1]."""

    evidence_gap: float
    environment_gap: float
    model_error: float
    frontier_opportunity: float

    def __post_init__(self) -> None:
        _validate_unit_fields(self.__dict__)


def _validate_unit_fields(fields: Mapping[str, float]) -> None:
    for name, value in fields.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]")


def maturity_score(inputs: MaturityInputs) -> float:
    """Compute capability-specific maturity M(c,t) from evidence, not age."""

    score = (
        0.25 * inputs.validation_stability
        + 0.20 * inputs.regression_resilience
        + 0.15 * inputs.environment_coverage
        + 0.15 * inputs.rollback_readiness
        + 0.15 * inputs.repeated_success
        + 0.10 * inputs.promotion_closure
    )
    return round(score, 6)


def uncertainty_score(inputs: UncertaintyInputs) -> float:
    """Compute unresolved uncertainty/opportunity U(c,t)."""

    score = (
        0.35 * inputs.evidence_gap
        + 0.30 * inputs.environment_gap
        + 0.20 * inputs.model_error
        + 0.15 * inputs.frontier_opportunity
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
    _validate_unit_fields({"maturity": maturity, "uncertainty": uncertainty})
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
    return round(max(mutation_floor, min(mutation_ceiling, budget)), 9)


@dataclass(frozen=True)
class MetaPolicy:
    min_occurrences: int
    min_confidence: float
    max_auto_risk: RiskClass
    require_deterministic_pass: bool
    require_rollback: bool
    allow_schema_mutation: bool = False
    allow_external_side_effects: bool = False


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
    source_meta_policy: str = "meta-automation-v1"
    status: str = "active"

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        _validate_unit_fields(
            {
                "maturity_score": self.maturity_score,
                "uncertainty_score": self.uncertainty_score,
                "confidence_floor": self.confidence_floor,
            }
        )
        if self.occurrence_floor < 1 or self.required_evidence_depth < 1:
            raise ValueError("evidence floors must be positive")
        if self.niche_occurrence_min < 1 or self.niche_replication_min < 1:
            raise ValueError("niche evidence floors must be positive")
        if self.status not in {"active", "superseded", "archived"}:
            raise ValueError("invalid envelope status")

    def respects(self, policy: MetaPolicy) -> bool:
        """A derived envelope may tighten but never loosen MetaPolicy."""

        return (
            self.confidence_floor >= policy.min_confidence
            and self.occurrence_floor >= policy.min_occurrences
            and _RISK_RANK[self.max_effective_risk] <= _RISK_RANK[policy.max_auto_risk]
        )


def select_active_envelope(
    capability_id: str,
    envelopes: Sequence[EvolutionEnvelope],
) -> EvolutionEnvelope:
    """Return the sole active lineage envelope; ambiguity is fail-closed."""

    active = [
        item
        for item in envelopes
        if item.capability_id == capability_id and item.status == "active"
    ]
    if len(active) != 1:
        raise ValueError(
            f"expected exactly one active envelope for {capability_id}; found {len(active)}"
        )
    return active[0]


def weighted_fit(deltas: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Compute Fit(x,e)=Σ w_j(e)Δ_j for one environment."""

    missing = set(weights) - set(deltas)
    if missing:
        raise ValueError(f"missing fit deltas: {sorted(missing)}")
    if any(weight < 0 for weight in weights.values()):
        raise ValueError("fit weights must be non-negative")
    return round(sum(weights[name] * deltas[name] for name in weights), 9)


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    authorized: bool
    risk_class: RiskClass
    confidence: float
    occurrence_count: int
    evidence_depth: int
    rollback_defined: bool
    deterministic_status: str | None
    protected_deltas: Mapping[str, float]
    current_fit_deltas: Mapping[str, float]
    current_fit_weights: Mapping[str, float]
    schema_mutation: bool = False
    external_side_effects: bool = False

    def current_fit(self) -> float:
        return weighted_fit(self.current_fit_deltas, self.current_fit_weights)


@dataclass(frozen=True)
class NicheEvidence:
    occurrences: int
    duration_days: float
    replications: int
    median_advantage: float
    fit_deltas: Mapping[str, float]
    fit_weights: Mapping[str, float]
    low_switching_cost: bool
    high_coexistence_cost: bool

    def fit(self) -> float:
        return weighted_fit(self.fit_deltas, self.fit_weights)


@dataclass(frozen=True)
class GateResult:
    disposition: GateDisposition
    reasons: tuple[str, ...]

    @property
    def hard_valid(self) -> bool:
        return self.disposition is GateDisposition.PASS


@dataclass(frozen=True)
class EvolutionDecision:
    disposition: EvolutionDisposition
    hard_valid: bool
    compatible: bool | None
    current_fit: float | None
    niche_fit: float | None
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
        if not candidate.authorized:
            return GateResult(
                GateDisposition.BLOCKED_UNAUTHORIZED,
                ("candidate lacks explicit authorization",),
            )
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
        if candidate.schema_mutation and not policy.allow_schema_mutation:
            return GateResult(
                GateDisposition.HUMAN_REVIEW_REQUIRED,
                ("candidate requests schema mutation outside autonomous policy",),
            )
        if candidate.external_side_effects and not policy.allow_external_side_effects:
            return GateResult(
                GateDisposition.HUMAN_REVIEW_REQUIRED,
                ("candidate requests external side effects outside autonomous policy",),
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

    def persistent_niche(self, niche: NicheEvidence, envelope: EvolutionEnvelope) -> bool:
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
        if not gate.hard_valid:
            return EvolutionDecision(
                EvolutionDisposition.REJECT_FROM_PROMOTION,
                False,
                None,
                None,
                None,
                None,
                gate,
                gate.reasons,
            )

        compatible = self.compatible(candidate, envelope)
        current_fit = candidate.current_fit()
        niche_fit = None if niche is None else niche.fit()
        niche_persistent = None if niche is None else self.persistent_niche(niche, envelope)

        if compatible and current_fit >= envelope.promotion_delta_min:
            return EvolutionDecision(
                EvolutionDisposition.PROMOTION_CANDIDATE,
                True,
                True,
                current_fit,
                niche_fit,
                niche_persistent,
                gate,
                ("validated compatible improvement exceeds promotion threshold",),
            )

        if niche is not None and niche_persistent and niche_fit is not None:
            if (
                compatible
                and niche_fit >= envelope.branch_delta_min
                and niche.low_switching_cost
            ):
                return EvolutionDecision(
                    EvolutionDisposition.POLYMORPH_CANDIDATE,
                    True,
                    True,
                    current_fit,
                    niche_fit,
                    True,
                    gate,
                    ("persistent niche advantage is compatible and cheaply selectable",),
                )
            if (
                not compatible
                and niche_fit >= envelope.branch_delta_min
                and niche.high_coexistence_cost
            ):
                return EvolutionDecision(
                    EvolutionDisposition.SPECIATION_CANDIDATE,
                    True,
                    False,
                    current_fit,
                    niche_fit,
                    True,
                    gate,
                    ("persistent niche advantage is useful but incompatible with parent form",),
                )

        return EvolutionDecision(
            EvolutionDisposition.REJECT_FROM_PROMOTION,
            True,
            compatible,
            current_fit,
            niche_fit,
            niche_persistent,
            gate,
            ("candidate has not cleared promotion, polymorphism, or speciation thresholds",),
        )
