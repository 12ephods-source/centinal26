from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Mapping

KERNEL_SCHEMA = "centinal26-evolution-kernel-v1"
KERNEL_VERSION = "1.0.0-draft"


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
    """Compute a deterministic normalized weighted score.

    The caller supplies both evidence components and policy weights. This keeps the
    evidence-to-score mapping explicit and hashable instead of embedding hidden
    calibration choices in code.
    """
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
    numerator = 0.0
    for name, weight in weights.items():
        numerator += _bounded(float(components[name]), name) * float(weight)
    return numerator / total_weight


@dataclass(frozen=True)
class EvolutionKernelPolicy:
    maturity_weights: dict[str, float]
    uncertainty_weights: dict[str, float]
    mutation_floor: float
    mutation_ceiling: float
    mutation_sensitivity: float
    confidence_floor: float
    occurrence_floor: int
    required_evidence_depth: int
    promotion_delta_min: float
    branch_delta_min: float
    niche_occurrence_min: int
    niche_duration_min_days: float
    niche_replication_min: int
    max_effective_risk: str = "LOW"

    def __post_init__(self) -> None:
        if self.mutation_floor < 0.0:
            raise ValueError("mutation_floor must be non-negative")
        if self.mutation_ceiling < self.mutation_floor:
            raise ValueError("mutation_ceiling must be >= mutation_floor")
        if self.mutation_sensitivity < 0.0:
            raise ValueError("mutation_sensitivity must be non-negative")
        _bounded(self.confidence_floor, "confidence_floor")
        if self.occurrence_floor < 1:
            raise ValueError("occurrence_floor must be >= 1")
        if self.required_evidence_depth < 1:
            raise ValueError("required_evidence_depth must be >= 1")
        if self.niche_occurrence_min < 1:
            raise ValueError("niche_occurrence_min must be >= 1")
        if self.niche_replication_min < 1:
            raise ValueError("niche_replication_min must be >= 1")
        if self.niche_duration_min_days < 0.0:
            raise ValueError("niche_duration_min_days must be non-negative")

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
    promotion_delta_min: float
    branch_delta_min: float
    niche_occurrence_min: int
    niche_duration_min_days: float
    niche_replication_min: int
    max_effective_risk: str
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
    source_meta_policy: str,
    source_policy_hash: str,
    source_evidence_hash: str,
) -> EvolutionEnvelope:
    """Compute M(c,t), U(c,t), and bounded mutation budget mu(c,t)."""
    if not capability_id:
        raise ValueError("capability_id may not be empty")
    if generation < 0:
        raise ValueError("generation must be non-negative")
    maturity = weighted_score(maturity_components, policy.maturity_weights)
    uncertainty = weighted_score(uncertainty_components, policy.uncertainty_weights)
    span = policy.mutation_ceiling - policy.mutation_floor
    mutation = policy.mutation_floor + (
        span
        * (1.0 - maturity)
        * uncertainty
        * policy.mutation_sensitivity
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


@dataclass(frozen=True)
class CandidateGovernanceEvidence:
    hard_valid: bool
    fit_score: float
    niche_fit_score: float
    protected_regressions: dict[str, float]
    regression_tolerances: dict[str, float]
    persistence: PersistenceEvidence


class EvolutionDecision(StrEnum):
    REJECT_FROM_PROMOTION = "REJECT_FROM_PROMOTION"
    PROMOTE = "PROMOTE"
    POLYMORPH = "POLYMORPH"
    SPECIATE = "SPECIATE"


@dataclass(frozen=True)
class GovernorResult:
    hard_valid: bool
    compatible: bool
    fit_score: float
    persistent: bool
    decision: EvolutionDecision
    reasons: tuple[str, ...]


def compatible_with_protected_metrics(evidence: CandidateGovernanceEvidence) -> bool:
    if not evidence.hard_valid:
        return False
    for metric, regression in evidence.protected_regressions.items():
        tolerance = evidence.regression_tolerances.get(metric)
        if tolerance is None:
            return False
        if float(regression) > float(tolerance):
            return False
    return True


def persistent_niche(
    evidence: PersistenceEvidence,
    policy: EvolutionKernelPolicy,
) -> bool:
    return (
        evidence.independent_occurrences >= policy.niche_occurrence_min
        and evidence.duration_days >= policy.niche_duration_min_days
        and evidence.independent_replications >= policy.niche_replication_min
    )


def govern_candidate(
    evidence: CandidateGovernanceEvidence,
    policy: EvolutionKernelPolicy,
) -> GovernorResult:
    """Apply the four-way constitutional governor.

    Positive fitness never compensates for failed hard validity or protected-metric
    incompatibility. Polymorphism/speciation require persistent niche evidence.
    """
    compatible = compatible_with_protected_metrics(evidence)
    persistent = persistent_niche(evidence.persistence, policy)
    reasons: list[str] = []

    if not evidence.hard_valid:
        reasons.append("hard_validation_failed")
    if evidence.hard_valid and not compatible:
        reasons.append("protected_metric_regression")

    if not compatible:
        decision = EvolutionDecision.REJECT_FROM_PROMOTION
    elif persistent and evidence.niche_fit_score >= policy.branch_delta_min:
        decision = EvolutionDecision.SPECIATE
        reasons.append("persistent_niche_exceeds_branch_delta")
    elif persistent and evidence.niche_fit_score >= policy.promotion_delta_min:
        decision = EvolutionDecision.POLYMORPH
        reasons.append("persistent_niche_supports_bounded_coexistence")
    elif evidence.fit_score >= policy.promotion_delta_min:
        decision = EvolutionDecision.PROMOTE
        reasons.append("compatible_global_fit_exceeds_promotion_delta")
    else:
        decision = EvolutionDecision.REJECT_FROM_PROMOTION
        reasons.append("fitness_below_promotion_threshold")

    return GovernorResult(
        hard_valid=evidence.hard_valid,
        compatible=compatible,
        fit_score=float(evidence.fit_score),
        persistent=persistent,
        decision=decision,
        reasons=tuple(reasons),
    )


def assert_unique_active_envelope(
    envelopes: list[Mapping[str, object]],
    *,
    capability_id: str,
    generation: int,
) -> None:
    active = [
        item
        for item in envelopes
        if item.get("capability_id") == capability_id
        and int(item.get("generation", -1)) == generation
        and item.get("status") == "active"
    ]
    if len(active) > 1:
        raise ValueError(
            f"multiple active envelopes for {capability_id} generation {generation}"
        )
