"""Truth-state and Bayesian update primitives for theory-search campaigns.

Bayesian belief is treated as a decision aid, never as a truth certificate.
Hard logical/structural falsification remains separate from probabilistic support.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class EpistemicClass(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    HYPOTHESIS = "HYPOTHESIS"
    REPORTED = "REPORTED"
    UNKNOWN = "UNKNOWN"


class TruthDisposition(str, Enum):
    SUPPORTED = "SUPPORTED"
    DISFAVORED = "DISFAVORED"
    FALSIFIED_IN_SCOPE = "FALSIFIED_IN_SCOPE"
    CONTRADICTED = "CONTRADICTED"
    UNRESOLVED = "UNRESOLVED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class DeterministicExperiment:
    experiment_id: str
    proposition: str
    expected_if_true: str
    expected_if_false: str
    scope: str
    assumptions: tuple[str, ...] = ()
    seed: int | None = None
    tolerance: float | None = None


@dataclass(frozen=True)
class ExperimentOutcome:
    experiment_id: str
    observed: str
    deterministic_pass: bool | None
    evidence_id: str
    notes: str = ""


@dataclass(frozen=True)
class BayesianUpdate:
    hypothesis_id: str
    prior: float
    likelihood_if_true: float
    likelihood_if_false: float
    posterior: float
    log_bayes_factor: float
    evidence_id: str


@dataclass
class BeliefState:
    """Calibrated belief bookkeeping over one explicit hypothesis.

    This class deliberately does not expose a "truth" flag. Posterior probability
    is conditional on the stated model, likelihoods, and evidence assumptions.
    """

    hypothesis_id: str
    probability: float
    updates: list[BayesianUpdate] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 < self.probability < 1.0:
            raise ValueError("probability must be strictly between 0 and 1")

    def update(
        self,
        *,
        likelihood_if_true: float,
        likelihood_if_false: float,
        evidence_id: str,
    ) -> BayesianUpdate:
        for value in (likelihood_if_true, likelihood_if_false):
            if not 0.0 <= value <= 1.0:
                raise ValueError("likelihoods must lie in [0, 1]")
        if likelihood_if_true == 0.0 and likelihood_if_false == 0.0:
            raise ValueError("evidence cannot be impossible under both hypotheses")

        prior = self.probability
        numerator = likelihood_if_true * prior
        denominator = numerator + likelihood_if_false * (1.0 - prior)
        if denominator == 0.0:
            raise ValueError("Bayesian update has zero normalizing evidence probability")
        posterior = numerator / denominator

        if likelihood_if_false == 0.0:
            log_bayes_factor = math.inf
        elif likelihood_if_true == 0.0:
            log_bayes_factor = -math.inf
        else:
            log_bayes_factor = math.log(likelihood_if_true / likelihood_if_false)

        result = BayesianUpdate(
            hypothesis_id=self.hypothesis_id,
            prior=prior,
            likelihood_if_true=likelihood_if_true,
            likelihood_if_false=likelihood_if_false,
            posterior=posterior,
            log_bayes_factor=log_bayes_factor,
            evidence_id=evidence_id,
        )
        self.probability = posterior
        self.updates.append(result)
        return result


@dataclass(frozen=True)
class TruthCompassReading:
    proposition: str
    epistemic_class: EpistemicClass
    disposition: TruthDisposition
    scope: str
    assumptions: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    posterior_support: float | None = None
    calibration_warning: str | None = None
    next_experiment: DeterministicExperiment | None = None


def calibrate_disposition(
    *,
    proposition: str,
    epistemic_class: EpistemicClass,
    scope: str,
    assumptions: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    hard_falsified: bool = False,
    contradictory: bool = False,
    blocked: bool = False,
    posterior_support: float | None = None,
    next_experiment: DeterministicExperiment | None = None,
) -> TruthCompassReading:
    """Return a fail-closed epistemic reading.

    Ordering is intentional: scoped falsification and contradiction dominate any
    Bayesian support value. Posterior support is never converted into truth.
    """
    if posterior_support is not None and not 0.0 <= posterior_support <= 1.0:
        raise ValueError("posterior_support must lie in [0, 1]")

    warning = None
    if hard_falsified:
        disposition = TruthDisposition.FALSIFIED_IN_SCOPE
    elif contradictory:
        disposition = TruthDisposition.CONTRADICTED
    elif blocked:
        disposition = TruthDisposition.BLOCKED
    elif posterior_support is None:
        disposition = TruthDisposition.UNRESOLVED
    elif posterior_support >= 0.95:
        disposition = TruthDisposition.SUPPORTED
        warning = "Probabilistic support is conditional and is not a truth certificate."
    elif posterior_support <= 0.05:
        disposition = TruthDisposition.DISFAVORED
        warning = "Probabilistic disfavour is conditional and is not a proof of falsity."
    else:
        disposition = TruthDisposition.UNRESOLVED

    return TruthCompassReading(
        proposition=proposition,
        epistemic_class=epistemic_class,
        disposition=disposition,
        scope=scope,
        assumptions=assumptions,
        evidence_ids=evidence_ids,
        posterior_support=posterior_support,
        calibration_warning=warning,
        next_experiment=next_experiment,
    )
