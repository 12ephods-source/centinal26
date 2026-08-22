from scripts.ftoe_so10_protected_i_so6_ew_embedding_gate import evaluate


def test_so6_second_doublet_low_energy_embedding_gate_passes():
    result = evaluate()
    assert result["pass"] is True
    assert all(result["checks"].values())
    assert result["scientific_status"] == "REVIEW"


def test_downstream_claims_remain_fail_closed():
    result = evaluate()
    assert result["checks"]["downstream_fail_closed"] is True
    assert "COMPATIBLE_REFERENCE_ONLY" in result["scientific_transition"]
