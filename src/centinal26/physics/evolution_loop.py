"""Bounded deterministic/Bayesian evolution loop for theory-search campaigns."""
from __future__ import annotations

from dataclasses import dataclass, field

from .truth_compass import (
    BeliefState,
    DeterministicExperiment,
    EpistemicClass,
    TruthCompassReading,
    calibrate_disposition,
)


@dataclass(frozen=True)
class ExperimentScore:
    experiment: DeterministicExperiment
    mandatory: bool
    family_elimination_power: int
    estimated_cost: int
    unresolved_relevance: int

    @property
    def priority(self) -> tuple[int, int, float, str]:
        # Deliberately rule-based rather than pseudo-calibrated information gain.
        efficiency = self.unresolved_relevance / max(self.estimated_cost, 1)
        return (
            1 if self.mandatory else 0,
            self.family_elimination_power,
            efficiency,
            self.experiment.experiment_id,
        )


@dataclass
class HypothesisState:
    hypothesis_id: str
    proposition: str
    scope: str
    assumptions: tuple[str, ...]
    belief: BeliefState
    hard_falsified: bool = False
    contradictory: bool = False
    blocked: bool = False
    evidence_ids: list[str] = field(default_factory=list)

    def reading(self, next_experiment: DeterministicExperiment | None = None) -> TruthCompassReading:
        return calibrate_disposition(
            proposition=self.proposition,
            epistemic_class=EpistemicClass.HYPOTHESIS,
            scope=self.scope,
            assumptions=self.assumptions,
            evidence_ids=tuple(self.evidence_ids),
            hard_falsified=self.hard_falsified,
            contradictory=self.contradictory,
            blocked=self.blocked,
            posterior_support=self.belief.probability,
            next_experiment=next_experiment,
        )


class BayesianEvolutionLoop:
    """Coordinates deterministic experiments and probabilistic hypothesis updates.

    The controller is intentionally conservative:
    - experiment selection is rule-based until empirical scheduler calibration exists;
    - hard falsification is never reversed by Bayesian support;
    - contradictory evidence prevents a supported disposition;
    - no method here promotes a scientific candidate lifecycle state.
    """

    def __init__(self, hypotheses: list[HypothesisState]) -> None:
        self.hypotheses = {h.hypothesis_id: h for h in hypotheses}

    def choose_next(self, scores: list[ExperimentScore]) -> DeterministicExperiment | None:
        if not scores:
            return None
        return max(scores, key=lambda score: score.priority).experiment

    def record_hard_result(
        self,
        hypothesis_id: str,
        *,
        evidence_id: str,
        falsified_in_scope: bool = False,
        contradictory: bool = False,
        blocked: bool = False,
    ) -> TruthCompassReading:
        state = self.hypotheses[hypothesis_id]
        state.evidence_ids.append(evidence_id)
        state.hard_falsified = state.hard_falsified or falsified_in_scope
        state.contradictory = state.contradictory or contradictory
        state.blocked = state.blocked or blocked
        return state.reading()

    def record_probabilistic_result(
        self,
        hypothesis_id: str,
        *,
        evidence_id: str,
        likelihood_if_true: float,
        likelihood_if_false: float,
    ) -> TruthCompassReading:
        state = self.hypotheses[hypothesis_id]
        state.belief.update(
            likelihood_if_true=likelihood_if_true,
            likelihood_if_false=likelihood_if_false,
            evidence_id=evidence_id,
        )
        state.evidence_ids.append(evidence_id)
        return state.reading()
