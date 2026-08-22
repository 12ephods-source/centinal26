from check_continuum_limit_contract import evaluate


def test_frozen_continuum_limit_audit() -> None:
    result = evaluate()
    assert result["execution_pass"] is True
    assert result["scientific_pass"] is False
    assert result["verdict"] == "UNRESOLVED_MISSING_INDUCTIVE_OR_INFINITE_PRODUCT_LIMIT_DATA"
    assert len(result["smallest_missing_inputs"]) == 4
