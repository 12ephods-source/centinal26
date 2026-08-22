from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum


class LifecycleStage(str, Enum):
    PROPOSED = "PROPOSED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    INDEPENDENTLY_VERIFIED = "INDEPENDENTLY_VERIFIED"
    DEVICE_VALIDATED = "DEVICE_VALIDATED"
    PERSISTENT_VALIDATED = "PERSISTENT_VALIDATED"
    PRODUCTION_READY = "PRODUCTION_READY"


_STAGE_ORDER = tuple(LifecycleStage)
_REQUIRED_EVIDENCE: dict[LifecycleStage, frozenset[str]] = {
    LifecycleStage.IMPLEMENTED: frozenset({"implementation_artifact"}),
    LifecycleStage.TESTED: frozenset({"implementation_artifact", "tests_pass"}),
    LifecycleStage.INDEPENDENTLY_VERIFIED: frozenset(
        {"implementation_artifact", "tests_pass", "independent_verification"}
    ),
    LifecycleStage.DEVICE_VALIDATED: frozenset(
        {
            "implementation_artifact",
            "tests_pass",
            "independent_verification",
            "device_origin",
        }
    ),
    LifecycleStage.PERSISTENT_VALIDATED: frozenset(
        {
            "implementation_artifact",
            "tests_pass",
            "independent_verification",
            "device_origin",
            "changed_boot_id",
            "persistence_verification",
        }
    ),
    LifecycleStage.PRODUCTION_READY: frozenset(
        {
            "implementation_artifact",
            "tests_pass",
            "independent_verification",
            "device_origin",
            "changed_boot_id",
            "persistence_verification",
            "production_acceptance",
        }
    ),
}


@dataclass(frozen=True)
class WorkCandidate:
    """One typed improvement candidate."""

    candidate_id: str
    capability: str
    expected_value: float = 0.0
    risk_reduction: float = 0.0
    dependency_unlock: float = 0.0
    human_labor_reduction: float = 0.0
    execution_cost: float = 0.0
    execution_risk: float = 0.0
    blocked_reason: str | None = None
    dependencies: tuple[str, ...] = ()

    def score(self) -> float:
        return (
            1.00 * self.expected_value
            + 1.20 * self.risk_reduction
            + 1.35 * self.dependency_unlock
            + 1.10 * self.human_labor_reduction
            - 0.65 * self.execution_cost
            - 0.90 * self.execution_risk
        )


@dataclass(frozen=True)
class RankedCandidate:
    candidate: WorkCandidate
    score: float


@dataclass
class CanonicalImprovementState:
    completed: set[str] = field(default_factory=set)
    evidence: set[str] = field(default_factory=set)
    lifecycle_stage: LifecycleStage = LifecycleStage.PROPOSED
    history: list[str] = field(default_factory=list)


class LifecycleGate:
    """Fail-closed lifecycle promotion, one stage at a time."""

    @staticmethod
    def next_stage(stage: LifecycleStage) -> LifecycleStage | None:
        idx = _STAGE_ORDER.index(stage)
        if idx + 1 >= len(_STAGE_ORDER):
            return None
        return _STAGE_ORDER[idx + 1]

    @classmethod
    def missing_evidence(
        cls, stage: LifecycleStage, evidence: Iterable[str]
    ) -> frozenset[str]:
        required = _REQUIRED_EVIDENCE.get(stage, frozenset())
        return required.difference(set(evidence))

    @classmethod
    def promote(cls, current: LifecycleStage, evidence: Iterable[str]) -> LifecycleStage:
        target = cls.next_stage(current)
        if target is None:
            return current
        missing = cls.missing_evidence(target, evidence)
        if missing:
            return current
        return target


class ImprovementController:
    """Deterministic selection and lifecycle controller.

    Execution authority deliberately remains outside this class. The controller
    selects only named capabilities; a registered bounded executor must perform
    mutation. This preserves plan != authorization != execution != verification.
    """

    @staticmethod
    def reconcile(
        candidates: Iterable[WorkCandidate],
        state: CanonicalImprovementState,
    ) -> list[WorkCandidate]:
        by_id: dict[str, WorkCandidate] = {}
        for candidate in candidates:
            existing = by_id.get(candidate.candidate_id)
            if existing is None or candidate.score() > existing.score():
                by_id[candidate.candidate_id] = candidate

        out: list[WorkCandidate] = []
        for candidate in by_id.values():
            if candidate.candidate_id in state.completed:
                continue
            if candidate.blocked_reason:
                continue
            if any(dep not in state.completed for dep in candidate.dependencies):
                continue
            out.append(candidate)
        return out

    @classmethod
    def rank(
        cls,
        candidates: Iterable[WorkCandidate],
        state: CanonicalImprovementState,
    ) -> list[RankedCandidate]:
        reconciled = cls.reconcile(candidates, state)
        ranked = [RankedCandidate(c, c.score()) for c in reconciled]
        ranked.sort(
            key=lambda item: (
                -item.score,
                item.candidate.execution_risk,
                item.candidate.execution_cost,
                item.candidate.candidate_id,
            )
        )
        return ranked

    @classmethod
    def select(
        cls,
        candidates: Iterable[WorkCandidate],
        state: CanonicalImprovementState,
    ) -> WorkCandidate | None:
        ranked = cls.rank(candidates, state)
        return ranked[0].candidate if ranked else None

    @staticmethod
    def record_completed(
        state: CanonicalImprovementState,
        candidate_id: str,
        *,
        evidence: Iterable[str] = (),
    ) -> None:
        if not candidate_id.strip():
            raise ValueError("candidate_id must not be empty")
        state.completed.add(candidate_id)
        state.evidence.update(x for x in evidence if x)
        state.history.append(f"completed:{candidate_id}")

    @staticmethod
    def attempt_promotion(state: CanonicalImprovementState) -> LifecycleStage:
        promoted = LifecycleGate.promote(state.lifecycle_stage, state.evidence)
        if promoted != state.lifecycle_stage:
            state.lifecycle_stage = promoted
            state.history.append(f"promoted:{promoted.value}")
        return state.lifecycle_stage
