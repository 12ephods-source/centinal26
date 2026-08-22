from centinal26.physics.local_eft4d import ScalarOperator, evaluate_basic_consistency, make_scalar_candidate
from centinal26.physics.theory_kernel import CandidateStatus, TestStatus, promotion_allowed


def test_candidate_identity_is_deterministic():
    ops = [ScalarOperator("chi2", 2, 2), ScalarOperator("chi4", 4, 0)]
    a = make_scalar_candidate(operators=ops, z2=True)
    b = make_scalar_candidate(operators=ops, z2=True)
    assert a.candidate_id == b.candidate_id
    assert a.theory.theory_id == b.theory.theory_id


def test_valid_fixture_passes_basic_consistency():
    c = make_scalar_candidate(
        operators=[ScalarOperator("kinetic", 4, 0), ScalarOperator("mass", 2, 2), ScalarOperator("quartic", 4, 0)],
        z2=True,
    )
    results = evaluate_basic_consistency(c)
    assert all(r.status is TestStatus.PASS for r in results)
    assert c.evidence_debt() == 0
    assert promotion_allowed(CandidateStatus.GENERATED, CandidateStatus.WELL_FORMED, c.evidence)
    assert promotion_allowed(CandidateStatus.WELL_FORMED, CandidateStatus.CONSISTENCY_SURVIVOR, c.evidence)


def test_dimensionally_invalid_fixture_fails_for_explicit_reason():
    c = make_scalar_candidate(operators=[ScalarOperator("bad_phi6", 6, 0)])
    results = evaluate_basic_consistency(c)
    dim = next(r for r in results if r.proposition == "dimensions_consistent")
    assert dim.status is TestStatus.FAIL
    assert dim.details["failing_operators"] == ["bad_phi6"]
    assert not promotion_allowed(CandidateStatus.WELL_FORMED, CandidateStatus.CONSISTENCY_SURVIVOR, c.evidence)


def test_nonreal_fixture_fails_reality_gate():
    c = make_scalar_candidate(operators=[ScalarOperator("complex_term", 4, 0, real=False)])
    results = evaluate_basic_consistency(c)
    reality = next(r for r in results if r.proposition == "reality_consistent")
    assert reality.status is TestStatus.FAIL


def test_empirical_promotion_fails_closed():
    c = make_scalar_candidate(operators=[ScalarOperator("kinetic", 4, 0)])
    evaluate_basic_consistency(c)
    assert not promotion_allowed(CandidateStatus.NUMERICAL_SURVIVOR, CandidateStatus.EMPIRICALLY_COMPARED, c.evidence)
    assert not promotion_allowed(CandidateStatus.EMPIRICALLY_COMPARED, CandidateStatus.SURVIVES_CURRENT_EVIDENCE, c.evidence)


def test_evidence_debt_counts_unresolved_obligations():
    c = make_scalar_candidate(operators=[ScalarOperator("bad", 6, 0)])
    evaluate_basic_consistency(c)
    assert c.evidence_debt({"dimensions_consistent": 5.0}) == 5.0
