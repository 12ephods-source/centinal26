from two_axis_weyl_bridge import evaluate


def test_two_axis_bridge_passes_frozen_numeric_gates() -> None:
    result = evaluate()
    assert result["execution_pass"] is True
    assert result["scientific_pass"] is False
    assert result["status"] == "PASS_TWO_AXIS_BOUNDED_WEYL_CORRELATOR_BRIDGE"


def test_d2_is_explicit_negative_control_for_continuum_bridge() -> None:
    result = evaluate()
    local = result["local_dimension_axis"]
    assert local["d2_worst_error"] >= 5.0e-2
    assert local["d32_worst_error"] <= 1.0e-8
    assert local["strictly_decreasing_worst_error"] is True


def test_spatial_axis_is_refined_and_second_order() -> None:
    result = evaluate()
    spatial = result["spatial_mode_axis"]
    assert spatial["continuum_reference_refinement"] <= 1.0e-10
    assert spatial["strictly_decreasing_error"] is True
    assert spatial["observed_convergence_order"] >= 1.8
    assert spatial["relative_errors"][-1] <= 2.0e-5
    assert spatial["max_final_weyl_error"] <= 5.0e-6


def test_promotion_ceiling_remains_local_observable_only() -> None:
    result = evaluate()
    not_established = result["interpretation"]["not_established"]
    assert "convergence of the entire local Weyl net" in not_established
    assert "derivation of the Type-III1 factor classification from the finite regulator" in not_established
    assert result["interpretation"]["next_gate"] == "LOCAL_NET_TOPOLOGY_AND_MODULAR_CONVERGENCE_CONTRACT"
