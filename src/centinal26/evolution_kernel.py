from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum

KERNEL_SCHEMA = "centinal26-evolution-kernel-v2"
KERNEL_VERSION = "2.0.0-draft"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bounded(value: float, name: str) -> float:
    rendered = float(value)
    if not 0.0 <= rendered <= 1.0:
        raise ValueError(f"{name} must be in [0,1]")
    return rendered


def weighted_score(
    components: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """Compute a deterministic normalized weighted score for bounded components."""
    if not weights:
        raise ValueError("weights may not be empty")
    missing = sorted(set(weights) - set(components))
    if missing:
        raise ValueError(f"missing evidence components: {missing}")
    if any(float(weight) < 0.0 for weight in weights.values()):
        raise ValueError("weights must be non-negative")
    total_weight = sum(float(weight) for weight in weights.values())
    if total_weight <= 0.0:
        raise ValueError("weights must have positive total")
    numerator = sum(
        _bounded(float(components[name]), name) * float(weight)
        for name, weight in weights.items()
    )
    return numerator / total_weight


def weighted_delta(deltas: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Compute Fit(x,e)=sum_j w_j(e)*Delta_j without hiding the metric weights."""
    if not weights:
        raise ValueError("fit weights may not be empty")
    missing = sorted(set(weights) - set(deltas))
    if missing:
        raise ValueError(f"missing fit deltas: {missing}")
    if any(float(weight) < 0.0 for weight in weights.values()):
        raise ValueError("fit weights must be non-negative")
    return sum(float(weights[name]) * float(deltas[name]) for name in weights)


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


class EvolutionDecision(StrEnum):
    REJECT_FROM_PROMOTION = "REJECT_FROM_PROMOTION"
    PROMOTE = "PROMOTE"
    POLYMORPH = "POLYMORPH"
    SPECIATE = "SPECIATE"


@dataclass(frozen=True)
class MetaPolicyConstraints:
    min_occurrences: int
    min_confidence: float
    max_auto_risk: RiskClass
    require_deterministic_pass: bool
    require_rollback: bool
    allow_schema_mutation: bool
    allow_external_side_effects: bool

    def __post_init__(self) -> None:
        if self.min_occurrences < 1:
            raise ValueError("min_occurrences must be >= 1")
        _bounded(self.min_confidence, "min_confidence")


@dataclass(frozen=True)
class EvolutionKernelPolicy:
    maturity_weights: dict[str, float]
    uncertainty_weights: dict[str, float]
    mutation_floor: float
    mutation_ceiling: float
    annealing_rate: float
    exploration_floor_fraction: float
    confidence_floor: float
    occurrence_floor: int
    required_evidence_depth: int
    regression_tolerances: dict[str, float]
    promotion_delta_min: float
    branch_delta_min: float
    niche_occurrence_min: int
    niche_duration_min_days: float
    niche_replication_min: int
    max_effective_risk: RiskClass = RiskClass.LOW

    def __post_init__(self) -> None:
        if self.mutation_floor < 0.0:
            raise ValueError("mutation_floor must be non-negative")
        if self.mutation_ceiling < self.mutation_floor:
            raise ValueError("mutation_ceiling must be >= mutation_floor")
        if self.annealing_rate < 0.0:
            raise ValueError("annealing_rate must be non-negative")
        _bounded(self.exploration_floor_fraction, "exploration_floor_fraction")
        _bounded(self.confidence_floor, "confidence_floor")
        if self.occurrence_floor < 1 or self.required_evidence_depth < 1:
            raise ValueError("evidence floors must be >= 1")
        if self.niche_occurrence_min < 1 or self.niche_replication_min < 1:
            raise ValueError("niche evidence floors must be >= 1")
        if self.niche_duration_min_days < 0.0:
            raise ValueError("niche_duration_min_days must be non-negative")
        if any(float(value) < 0.0 for value in self.regression_tolerances.values()):
            raise ValueError("regression tolerances must be non-negative")

    def respects(self, meta_policy: MetaPolicyConstraints) -> bool:
        return (
            self.confidence_floor >= meta_policy.min_confidence
            and self.occurrence_floor >= meta_policy.min_occurrences
            and _RISK_RANK[self.max_effective_risk]
            <= _RISK_RANK[meta_policy.max_auto_risk]
        )

    def digest(self) -> str:
        return _canonical_sha256(
            {
                "schema": KERNEL_SCHEMA,
                "kernel_version": KERNEL_VERSION,
                "policy": asdict(self),
            }
        )


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
    required_evidence_depth: int
    regression_tolerances: dict[str, float]
    promotion_delta_min: float
    branch_delta_min: float
    niche_occurrence_min: int
    niche_duration_min_days: float
    niche_replication_min: int
    max_effective_risk: RiskClass
    source_meta_policy: str
    source_policy_hash: str
    source_evidence_hash: str
    kernel_version: str
    kernel_hash: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def compute_envelope(
    *,
    capability_id: str,
    generation: int,
    maturity_components: Mapping[str, float],
    uncertainty_components: Mapping[str, float],
    policy: EvolutionKernelPolicy,
    meta_policy: MetaPolicyConstraints,
    source_meta_policy: str,
    source_policy_hash: str,
    source_evidence_hash: str,
) -> EvolutionEnvelope:
    """Compute M(c,t), U(c,t), and capability-specific differential plasticity."""
    if not capability_id:
        raise ValueError("capability_id may not be empty")
    if generation < 0:
        raise ValueError("generation must be non-negative")
    if not policy.respects(meta_policy):
        raise ValueError("evolution policy loosens its source MetaPolicy")

    maturity = weighted_score(maturity_components, policy.maturity_weights)
    uncertainty = weighted_score(uncertainty_components, policy.uncertainty_weights)
    uncertainty_factor = policy.exploration_floor_fraction + (
        (1.0 - policy.exploration_floor_fraction) * uncertainty
    )
    span = policy.mutation_ceiling - policy.mutation_floor
    mutation = policy.mutation_floor + (
        span * math.exp(-policy.annealing_rate * maturity) * uncertainty_factor
    )
    mutation = min(policy.mutation_ceiling, max(policy.mutation_floor, mutation))

    return EvolutionEnvelope(
        capability_id=capability_id,
        generation=generation,
        maturity_score=maturity,
        uncertainty_score=uncertainty,
        mutation_floor=policy.mutation_floor,
        mutation_ceiling=policy.mutation_ceiling,
        effective_mutation_budget=mutation,
        confidence_floor=policy.confidence_floor,
        occurrence_floor=policy.occurrence_floor,
        required_evidence_depth=policy.required_evidence_depth,
        regression_tolerances=dict(policy.regression_tolerances),
        promotion_delta_min=policy.promotion_delta_min,
        branch_delta_min=policy.branch_delta_min,
        niche_occurrence_min=policy.niche_occurrence_min,
        niche_duration_min_days=policy.niche_duration_min_days,
        niche_replication_min=policy.niche_replication_min,
        max_effective_risk=policy.max_effective_risk,
        source_meta_policy=source_meta_policy,
        source_policy_hash=source_policy_hash,
        source_evidence_hash=source_evidence_hash,
        kernel_version=KERNEL_VERSION,
        kernel_hash=policy.digest(),
    )


@dataclass(frozen=True)
class PersistenceEvidence:
    independent_occurrences: int
    duration_days: float
    independent_replications: int
    median_advantage: float


@dataclass(frozen=True)
class CandidateGovernanceEvidence:
    candidate_id: str
    authorized: bool
    risk_class: RiskClass
    confidence: float
    occurrence_count: int
    evidence_depth: int
    rollback_defined: bool
    deterministic_status: str | None
    schema_mutation: bool
    external_side_effects: bool
    protected_deltas: dict[str, float]
    current_fit_deltas: dict[str, float]
    current_fit_weights: dict[str, float]
    niche_fit_deltas: dict[str, float]
    niche_fit_weights: dict[str, float]
    persistence: PersistenceEvidence
    low_switching_cost: bool
    high_coexistence_cost: bool


@dataclass(frozen=True)
class GateResult:
    disposition: GateDisposition
    reasons: tuple[str, ...]

    @property
    def hard_valid(self) -> bool:
        return self.disposition is GateDisposition.PASS


@dataclass(frozen=True)
class GovernorResult:
    hard_valid: bool
    compatible: bool | None
    fit_score: float | None
    niche_fit_score: float | None
    persistent: bool | None
    decision: EvolutionDecision
    gate: GateResult
    reasons: tuple[str, ...]


def constitutional_gate(
    evidence: CandidateGovernanceEvidence,
    envelope: EvolutionEnvelope,
    meta_policy: MetaPolicyConstraints,
) -> GateResult:
    if not evidence.authorized:
        return GateResult(
            GateDisposition.BLOCKED_UNAUTHORIZED,
            ("candidate lacks explicit authorization",),
        )
    if evidence.deterministic_status == "FAIL":
        return GateResult(
            GateDisposition.REJECT_VALIDATION_FAILED,
            ("deterministic validation explicitly failed",),
        )
    if meta_policy.require_deterministic_pass and evidence.deterministic_status != "PASS":
        return GateResult(
            GateDisposition.BLOCKED_PENDING_VALIDATION,
            ("MetaPolicy requires an explicit deterministic PASS",),
        )
    if meta_policy.require_rollback and not evidence.rollback_defined:
        return GateResult(
            GateDisposition.BLOCKED_ROLLBACK_REQUIRED,
            ("MetaPolicy requires a defined rollback",),
        )
    if evidence.schema_mutation and not meta_policy.allow_schema_mutation:
        return GateResult(
            GateDisposition.HUMAN_REVIEW_REQUIRED,
            ("candidate requests schema mutation outside autonomous policy",),
        )
    if evidence.external_side_effects and not meta_policy.allow_external_side_effects:
        return GateResult(
            GateDisposition.HUMAN_REVIEW_REQUIRED,
            ("candidate requests external side effects outside autonomous policy",),
        )
    if evidence.confidence < envelope.confidence_floor:
        return GateResult(
            GateDisposition.BLOCKED_INSUFFICIENT_EVIDENCE,
            ("candidate confidence is below the derived envelope floor",),
        )
    if evidence.occurrence_count < envelope.occurrence_floor:
        return GateResult(
            GateDisposition.BLOCKED_INSUFFICIENT_EVIDENCE,
            ("independent occurrence count is below the derived envelope floor",),
        )
    if evidence.evidence_depth < envelope.required_evidence_depth:
        return GateResult(
            GateDisposition.BLOCKED_INSUFFICIENT_EVIDENCE,
            ("validated evidence depth is below the derived envelope floor",),
        )
    if _RISK_RANK[evidence.risk_class] > _RISK_RANK[envelope.max_effective_risk]:
        return GateResult(
            GateDisposition.HUMAN_REVIEW_REQUIRED,
            ("candidate risk exceeds the autonomous envelope",),
        )
    return GateResult(GateDisposition.PASS, ())


def compatible_with_protected_metrics(
    evidence: CandidateGovernanceEvidence,
    envelope: EvolutionEnvelope,
) -> bool:
    missing = sorted(set(envelope.regression_tolerances) - set(evidence.protected_deltas))
    if missing:
        raise ValueError(f"missing protected deltas: {missing}")
    return all(
        float(evidence.protected_deltas[metric]) >= -float(tolerance)
        for metric, tolerance in envelope.regression_tolerances.items()
    )


def persistent_niche(
    evidence: PersistenceEvidence,
    envelope: EvolutionEnvelope,
) -> bool:
    return (
        evidence.independent_occurrences >= envelope.niche_occurrence_min
        and evidence.duration_days >= envelope.niche_duration_min_days
        and evidence.independent_replications >= envelope.niche_replication_min
        and evidence.median_advantage >= envelope.branch_delta_min
    )


def govern_candidate(
    evidence: CandidateGovernanceEvidence,
    envelope: EvolutionEnvelope,
    meta_policy: MetaPolicyConstraints,
) -> GovernorResult:
    """Apply the constitutional gate, then the four-way Dragon Evolution decision."""
    gate = constitutional_gate(evidence, envelope, meta_policy)
    if not gate.hard_valid:
        return GovernorResult(
            hard_valid=False,
            compatible=None,
            fit_score=None,
            niche_fit_score=None,
            persistent=None,
            decision=EvolutionDecision.REJECT_FROM_PROMOTION,
            gate=gate,
            reasons=gate.reasons,
        )

    compatible = compatible_with_protected_metrics(evidence, envelope)
    fit_score = weighted_delta(evidence.current_fit_deltas, evidence.current_fit_weights)
    niche_fit_score = weighted_delta(evidence.niche_fit_deltas, evidence.niche_fit_weights)
    persistent = persistent_niche(evidence.persistence, envelope)

    if compatible and fit_score >= envelope.promotion_delta_min:
        decision = EvolutionDecision.PROMOTE
        reasons = ("compatible current-environment Fit exceeds promotion threshold",)
    elif (
        compatible
        and persistent
        and niche_fit_score >= envelope.branch_delta_min
        and evidence.low_switching_cost
    ):
        decision = EvolutionDecision.POLYMORPH
        reasons = ("persistent compatible niche is cheaply selectable",)
    elif (
        not compatible
        and persistent
        and niche_fit_score >= envelope.branch_delta_min
        and evidence.high_coexistence_cost
    ):
        decision = EvolutionDecision.SPECIATE
        reasons = ("persistent useful niche is incompatible and costly to coexist",)
    else:
        decision = EvolutionDecision.REJECT_FROM_PROMOTION
        reasons = ("candidate has not cleared promotion, polymorphism, or speciation gates",)

    return GovernorResult(
        hard_valid=True,
        compatible=compatible,
        fit_score=fit_score,
        niche_fit_score=niche_fit_score,
        persistent=persistent,
        decision=decision,
        gate=gate,
        reasons=reasons,
    )


def select_unique_active_envelope(
    envelopes: Sequence[Mapping[str, object]],
    *,
    capability_id: str,
) -> Mapping[str, object]:
    active = [
        item
        for item in envelopes
        if item.get("capability_id") == capability_id and item.get("status") == "active"
    ]
    if len(active) != 1:
        raise ValueError(
            f"expected exactly one active envelope for {capability_id}; found {len(active)}"
        )
    return active[0]
