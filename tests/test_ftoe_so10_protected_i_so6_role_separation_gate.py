import json
from pathlib import Path

from scripts.ftoe_so10_protected_i_so6_role_separation_gate import evaluate


def test_role_separated_reference_contract_passes() -> None:
    candidate = json.loads(
        Path("physics/ftoe/protected_I_so6_role_separated_candidate_v14.json").read_text(encoding="utf-8")
    )
    result = evaluate(candidate)
    assert result["gate"] == "ROLE_SEPARATED_REFERENCE_MECHANISM_STRUCTURALLY_SPECIFIED"
    assert result["scientific_status"] == "REVIEW"
    assert all(result["checks"].values())


def test_fails_closed_if_fToe_specific_gate_is_claimed_derived() -> None:
    candidate = json.loads(
        Path("physics/ftoe/protected_I_so6_role_separated_candidate_v14.json").read_text(encoding="utf-8")
    )
    candidate["mandatory_gates"]["mu_I_13p5_TeV_mass_matching"] = "DERIVED"
    result = evaluate(candidate)
    assert result["gate"] == "FAIL_REFERENCE_STRUCTURE_CONTRACT"
