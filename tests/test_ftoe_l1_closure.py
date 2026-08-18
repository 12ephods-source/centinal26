from centinal26.ftoe_l1_closure import L1Inputs, evaluate_l1, operator_scan, preferred_operator


def test_preferred_planck_suppression_is_nine_with_order_one_coefficient():
    op = preferred_operator(L1Inputs())
    assert op.suppression_power == 9
    assert 0.3 < op.wilson_coefficient < 0.33


def test_operator_scan_keeps_lower_dimension_threats_visible():
    scan = operator_scan(L1Inputs())
    assert scan[0].suppression_power == 1
    assert scan[-1].suppression_power == 12
    assert len(scan) == 12


def test_existing_mu_to_beta_chain_reproduces_target_numerically():
    result = evaluate_l1()
    assert 3.8e11 < result.lambda_x_gev < 3.9e11
    assert 0.98e-15 < result.beta < 1.02e-15
    assert result.gates["noncircular_beta_chain_numerics"] == "PASS"


def test_unproven_uv_gates_prevent_false_scientific_pass():
    result = evaluate_l1()
    assert result.gates["explicit_protecting_symmetry"] == "NOT_TESTED"
    assert result.gates["lower_dimension_operator_exclusion"] == "NOT_TESTED"
    assert result.overall == "REVIEW"


def test_full_pass_requires_every_mandatory_uv_gate():
    result = evaluate_l1(
        protecting_symmetry_gate="PASS",
        lower_operator_exclusion_gate="PASS",
        vacuum_solution_gate="PASS",
        threshold_backreaction_gate="PASS",
    )
    assert result.overall == "PASS"


def test_a_mandatory_failed_gate_forces_fail():
    result = evaluate_l1(protecting_symmetry_gate="FAIL")
    assert result.overall == "FAIL"
