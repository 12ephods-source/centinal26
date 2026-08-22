import pytest

from centinal26.physics.local_eft4d import (
    LocalScalarEFT4D,
    MetricConvention,
    Parameter,
    ScalarTerm,
    make_scalar_candidate,
)
from centinal26.physics.theory_kernel import CandidateStatus, PropositionEvidence, TestStatus
from centinal26.physics.theory_testing import PhysicsTheoryTestingEngine, SCOPE


def kinetic(sign: int = -1) -> ScalarTerm:
    return ScalarTerm("kinetic", 2, 2, Parameter("half", 0), sign)


def test_phi4_model_passes_structural_engine():
    model = LocalScalarEFT4D(
        terms=(
            kinetic(),
            ScalarTerm("mass", 2, 0, Parameter("m2", 2), -1),
            ScalarTerm("quartic", 4, 0, Parameter("lambda", 0), -1),
        ),
        z2=True,
    )
    candidate = make_scalar_candidate(model)
    results = PhysicsTheoryTestingEngine().evaluate(candidate)
    assert all(result.status is TestStatus.PASS for result in results)
    candidate.transition(CandidateStatus.WELL_FORMED)
    candidate.transition(CandidateStatus.STRUCTURALLY_CHECKED)
    assert candidate.evidence_debt() == 0


def test_phi6_suppressed_by_cutoff_passes_dimension_gate():
    model = LocalScalarEFT4D(
        terms=(kinetic(), ScalarTerm("phi6", 6, 0, Parameter("c6_over_lambda2", -2), -1)),
        z2=True,
    )
    candidate = make_scalar_candidate(model)
    results = PhysicsTheoryTestingEngine().evaluate(candidate)
    dimension = next(result for result in results if result.proposition == "dimensions_consistent")
    assert dimension.status is TestStatus.PASS


def test_phi6_with_dimensionless_coefficient_fails_dimension_gate():
    model = LocalScalarEFT4D(
        terms=(kinetic(), ScalarTerm("bad_phi6", 6, 0, Parameter("c6", 0), -1)),
        z2=True,
    )
    candidate = make_scalar_candidate(model)
    results = PhysicsTheoryTestingEngine().evaluate(candidate)
    dimension = next(result for result in results if result.proposition == "dimensions_consistent")
    assert dimension.status is TestStatus.FAIL
    assert dimension.details["failing_terms"] == ["bad_phi6"]


def test_declared_z2_rejects_phi3():
    model = LocalScalarEFT4D(
        terms=(kinetic(), ScalarTerm("phi3", 3, 0, Parameter("mu", 1), -1)),
        z2=True,
    )
    candidate = make_scalar_candidate(model)
    results = PhysicsTheoryTestingEngine().evaluate(candidate)
    symmetry = next(result for result in results if result.proposition == "declared_symmetries_respected")
    assert symmetry.status is TestStatus.FAIL
    assert symmetry.details["failing_terms"] == ["phi3"]


def test_wrong_kinetic_sign_fails_under_declared_metric():
    model = LocalScalarEFT4D(
        terms=(kinetic(sign=1),),
        metric=MetricConvention.MOSTLY_PLUS,
    )
    candidate = make_scalar_candidate(model)
    results = PhysicsTheoryTestingEngine().evaluate(candidate)
    kinetic_result = next(result for result in results if result.proposition == "kinetic_sign_consistent")
    assert kinetic_result.status is TestStatus.FAIL


def test_operator_order_does_not_change_theory_identity():
    a = ScalarTerm("mass", 2, 0, Parameter("m2", 2), -1)
    b = ScalarTerm("quartic", 4, 0, Parameter("lambda", 0), -1)
    first = make_scalar_candidate(LocalScalarEFT4D(terms=(kinetic(), a, b)))
    second = make_scalar_candidate(LocalScalarEFT4D(terms=(b, kinetic(), a)))
    assert first.theory_content_id == second.theory_content_id


def test_lineage_changes_instance_identity_not_theory_identity():
    model = LocalScalarEFT4D(terms=(kinetic(),))
    first = make_scalar_candidate(model)
    second = make_scalar_candidate(model)
    second.parents.append("parent")
    second.lineage_event_id = "mutation-1"
    assert first.theory_content_id == second.theory_content_id
    assert first.candidate_instance_id != second.candidate_instance_id


def test_engine_is_idempotent_for_same_inputs():
    candidate = make_scalar_candidate(LocalScalarEFT4D(terms=(kinetic(),)))
    engine = PhysicsTheoryTestingEngine()
    engine.evaluate(candidate)
    first_count = len(candidate.evidence)
    engine.evaluate(candidate)
    assert len(candidate.evidence) == first_count


def test_illegal_lifecycle_skip_is_rejected():
    candidate = make_scalar_candidate(LocalScalarEFT4D(terms=(kinetic(),)))
    PhysicsTheoryTestingEngine().evaluate(candidate)
    with pytest.raises(ValueError, match="illegal transition"):
        candidate.transition(CandidateStatus.STRUCTURALLY_CHECKED)


def test_scoped_pass_cannot_discharge_obligation():
    candidate = make_scalar_candidate(LocalScalarEFT4D(terms=(kinetic(),)))
    foreign = PropositionEvidence(
        proposition="well_formed",
        scope="different scope",
        assumptions=(),
        method="fixture",
        status=TestStatus.PASS,
        evidence_type="structural_check",
        validator_id="fixture",
        validator_version="1",
        input_hash="x",
    )
    candidate.add_evidence(foreign)
    assert candidate.evidence_debt() == 4.0
    with pytest.raises(ValueError, match="proof obligations"):
        candidate.transition(CandidateStatus.WELL_FORMED)


def test_active_fail_blocks_obligation_even_with_pass():
    candidate = make_scalar_candidate(LocalScalarEFT4D(terms=(kinetic(),)))
    PhysicsTheoryTestingEngine().evaluate(candidate)
    failing = PropositionEvidence(
        proposition="well_formed",
        scope=SCOPE,
        assumptions=(),
        method="adversarial recheck",
        status=TestStatus.FAIL,
        evidence_type="structural_check",
        validator_id="physics.local_scalar_eft.well_formed",
        validator_version="2.1",
        input_hash=candidate.domain_model.input_hash,
        details={"reason": "deliberate contradiction fixture"},
    )
    candidate.add_evidence(failing)
    obligation = next(o for o in candidate.obligations if o.proposition == "well_formed")
    assert not candidate.obligation_discharged(obligation)


def test_empirical_promotion_is_not_available_in_theory_kernel():
    candidate = make_scalar_candidate(LocalScalarEFT4D(terms=(kinetic(),)))
    PhysicsTheoryTestingEngine().evaluate(candidate)
    candidate.transition(CandidateStatus.WELL_FORMED)
    candidate.transition(CandidateStatus.STRUCTURALLY_CHECKED)
    with pytest.raises(ValueError, match="illegal transition"):
        candidate.transition(CandidateStatus.EMPIRICALLY_COMPARED)
