from powers_type_iii_control import PowersControl


def test_product_state_and_ratio_contract() -> None:
    result = PowersControl(0.25).evaluate(8)
    assert result["execution_pass"] is True
    assert result["scientific_pass"] is False
    assert result["control_classification"] == "KNOWN_POWERS_TYPE_III_LAMBDA_CONTROL"
    assert result["max_state_compatibility_residual"] <= 1e-15
    assert result["max_local_modular_ratio_error"] <= 1e-14


def test_embedding_compatibility_is_exact_to_roundoff() -> None:
    assert PowersControl(0.37).state_compatibility_residual(0.12345) <= 1e-15


def test_modular_ratio_matches_integer_lambda_power() -> None:
    model = PowersControl(0.2)
    left = (1, 0, 1, 1)
    right = (0, 1, 0, 0)
    assert model.modular_exponent(left, right) == 2
    assert abs(model.modular_ratio(left, right) - 0.2**2) <= 1e-15


def test_invalid_lambda_fails_closed() -> None:
    for value in (0.0, 1.0, -0.2, 1.2):
        try:
            PowersControl(value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid lambda was accepted")
