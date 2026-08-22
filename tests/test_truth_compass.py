import math

import pytest

from centinal26.physics.truth_compass import (
    BeliefState,
    DeterministicExperiment,
    EpistemicClass,
    TruthDisposition,
    calibrate_disposition,
)


def test_bayesian_update_is_deterministic():
    belief = BeliefState("H1", 0.5)
    update = belief.update(
        likelihood_if_true=0.9,
        likelihood_if_false=0.1,
        evidence_id="E1",
    )
    assert update.posterior == pytest.approx(0.9)
    assert update.log_bayes_factor == pytest.approx(math.log(9.0))
    assert belief.probability == pytest.approx(0.9)


def test_hard_falsification_overrides_high_posterior_support():
    reading = calibrate_disposition(
        proposition="fixture",
        epistemic_class=EpistemicClass.HYPOTHESIS,
        scope="bounded fixture scope",
        assumptions=(),
        evidence_ids=("E1",),
        hard_falsified=True,
        posterior_support=0.999,
    )
    assert reading.disposition is TruthDisposition.FALSIFIED_IN_SCOPE


def test_contradiction_prevents_supported_label():
    reading = calibrate_disposition(
        proposition="fixture",
        epistemic_class=EpistemicClass.DERIVED,
        scope="fixture scope",
        assumptions=(),
        evidence_ids=("E1", "E2"),
        contradictory=True,
        posterior_support=0.99,
    )
    assert reading.disposition is TruthDisposition.CONTRADICTED


def test_supported_probability_carries_calibration_warning():
    reading = calibrate_disposition(
        proposition="fixture",
        epistemic_class=EpistemicClass.INFERRED,
        scope="fixture scope",
        assumptions=("model class fixed",),
        evidence_ids=("E1",),
        posterior_support=0.97,
    )
    assert reading.disposition is TruthDisposition.SUPPORTED
    assert reading.calibration_warning is not None


def test_next_deterministic_experiment_is_preserved():
    experiment = DeterministicExperiment(
        experiment_id="X1",
        proposition="dimensions_consistent",
        expected_if_true="all represented terms have dimension four",
        expected_if_false="at least one represented term differs from dimension four",
        scope="LocalScalarEFT4D/v2",
        seed=0,
        tolerance=0.0,
    )
    reading = calibrate_disposition(
        proposition="dimensions_consistent",
        epistemic_class=EpistemicClass.DERIVED,
        scope="LocalScalarEFT4D/v2",
        assumptions=("natural units",),
        evidence_ids=(),
        next_experiment=experiment,
    )
    assert reading.disposition is TruthDisposition.UNRESOLVED
    assert reading.next_experiment == experiment


def test_invalid_likelihood_is_rejected():
    belief = BeliefState("H1", 0.5)
    with pytest.raises(ValueError, match="likelihoods"):
        belief.update(
            likelihood_if_true=1.2,
            likelihood_if_false=0.1,
            evidence_id="E1",
        )
