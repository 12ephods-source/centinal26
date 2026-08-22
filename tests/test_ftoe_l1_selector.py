from centinal26.ftoe_l1_selector import (
    CyclicSelector,
    dimension_13_candidate_allowed,
    lower_breaking_powers_forbidden,
    minimal_selector_for_first_power,
    scalar_only_discrete_anomaly_status,
)


def test_minimal_unit_charge_selector_for_nine_is_z9():
    selector = minimal_selector_for_first_power(9)
    assert selector == CyclicSelector(order=9, spurion_charge=1)


def test_z9_forbids_all_lower_spurion_powers_and_allows_nine():
    selector = CyclicSelector(9)
    assert lower_breaking_powers_forbidden(selector)
    assert dimension_13_candidate_allowed(selector)
    assert selector.first_positive_invariant_power() == 9


def test_selector_is_not_misclassified_as_mass_protection():
    assert scalar_only_discrete_anomaly_status(chiral_fermions_charged=False) == "PASS_CONDITIONAL"
    assert scalar_only_discrete_anomaly_status(chiral_fermions_charged=True) == "REVIEW"
