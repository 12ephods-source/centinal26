import json
from pathlib import Path

from scripts import ftoe_so10_protected_i_candidate_gate as gate

ROOT = Path(__file__).resolve().parents[1]


def test_current_candidate_fails_closed():
    result = gate.evaluate(gate.load_candidate())
    assert result["candidate_admission"] == "FAIL_CURRENT_CANDIDATE"
    assert result["gates"]["explicit_nonlinear_coset"] == "PASS"
    assert result["gates"]["I_doublet_identification"] == "PASS"
    assert result["gates"]["reference_bound_reproduced"] == "PASS"
    assert result["gates"]["protection_scale_frozen"] == "FAIL"
    assert result["gates"]["renormalizable_SO10_portal_suppression"] == "FAIL"
    assert result["gates"]["beta_function_backreaction"] == "FAIL"


def test_synthetic_fully_closed_candidate_can_pass_structure():
    candidate = json.loads(json.dumps(gate.load_candidate()))
    candidate["protection_scale_f_GeV"] = 1.0e5
    for key in (
        "gauge_embedding_and_hypercharge",
        "collective_or_other_radiative_protection",
        "representation_specific_C",
        "renormalizable_SO10_portal_suppression",
        "strong_sector_resonance_spectrum",
        "beta_function_backreaction",
        "matching_to_existing_mu_I_and_G422_branch",
    ):
        candidate["mandatory_admission_gates"][key] = "DERIVED"
    result = gate.evaluate(candidate)
    assert result["candidate_admission"] == "PASS"


def test_reference_bound_rejects_scale_above_break_even():
    candidate = json.loads(json.dumps(gate.load_candidate()))
    candidate["protection_scale_f_GeV"] = 2.0e5
    result = gate.evaluate(candidate)
    assert result["gates"]["protection_scale_frozen"] == "PASS"
    assert result["gates"]["protection_scale_within_reference_bound"] == "FAIL"
