from centinal26.physics.evolution_loop import (
    BayesianEvolutionLoop,
    ExperimentScore,
    HypothesisState,
)
from centinal26.physics.truth_compass import (
    BeliefState,
    DeterministicExperiment,
    TruthDisposition,
)


def experiment(name: str) -> DeterministicExperiment:
    return DeterministicExperiment(
        experiment_id=name,
        proposition="fixture",
        expected_if_true="pass",
        expected_if_false="fail",
        scope="fixture",
    )


def test_scheduler_prefers_mandatory_then_elimination_power():
    loop = BayesianEvolutionLoop([])
    low = ExperimentScore(experiment("low"), False, 100, 1, 100)
    mandatory = ExperimentScore(experiment("mandatory"), True, 1, 100, 1)
    assert loop.choose_next([low, mandatory]).experiment_id == "mandatory"


def test_hard_falsification_dominates_posterior():
    state = HypothesisState("H1", "fixture", "fixture", (), BeliefState("H1", 0.99))
    loop = BayesianEvolutionLoop([state])
    reading = loop.record_hard_result("H1", evidence_id="E-hard", falsified_in_scope=True)
    assert reading.disposition is TruthDisposition.FALSIFIED_IN_SCOPE
    assert reading.posterior_support == 0.99


def test_bayesian_update_changes_belief_without_promoting_truth():
    state = HypothesisState("H1", "fixture", "fixture", (), BeliefState("H1", 0.5))
    loop = BayesianEvolutionLoop([state])
    reading = loop.record_probabilistic_result(
        "H1",
        evidence_id="E-prob",
        likelihood_if_true=0.9,
        likelihood_if_false=0.1,
    )
    assert reading.posterior_support == 0.9
    assert reading.disposition is TruthDisposition.UNRESOLVED


def test_contradiction_blocks_supported_disposition():
    state = HypothesisState("H1", "fixture", "fixture", (), BeliefState("H1", 0.99))
    loop = BayesianEvolutionLoop([state])
    reading = loop.record_hard_result("H1", evidence_id="E-contradiction", contradictory=True)
    assert reading.disposition is TruthDisposition.CONTRADICTED
