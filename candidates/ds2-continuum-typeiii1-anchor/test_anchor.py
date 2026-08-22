from check_anchor import evaluate


def test_source_anchor_contract_is_fail_closed() -> None:
    result = evaluate()
    assert result["execution_pass"] is True
    assert result["scientific_pass"] is False
    assert result["verdict"] == "PASS_DS2_CONTINUUM_TYPE_III1_SOURCE_ANCHOR"
    assert result["continuum_target"]["local_factor_type"] == "HYPERFINITE_TYPE_III_1"
    assert result["next_gate"] == "TWO_AXIS_WEYL_BRIDGE_LOCAL_DIMENSION_THEN_MODE_LIMIT"
    assert len(result["unresolved_bridge"]) >= 4
