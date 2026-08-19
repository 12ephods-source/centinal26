import json
from pathlib import Path
from scripts.ftoe_so10_protected_i_littlest_higgs_gate import evaluate


def test_versioned_reference_candidate_is_structurally_specified():
    p = Path("physics/ftoe/protected_I_littlest_higgs_candidate_v07.json")
    result = evaluate(json.loads(p.read_text(encoding="utf-8")))
    assert result["gate"] == "REFERENCE_COLLECTIVE_MECHANISM_STRUCTURALLY_SPECIFIED"
    assert result["scientific_status"] == "REVIEW"
    assert all(result["checks"].values())


def test_missing_open_compatibility_gate_fails_closed():
    p = Path("physics/ftoe/protected_I_littlest_higgs_candidate_v07.json")
    candidate = json.loads(p.read_text(encoding="utf-8"))
    candidate["mandatory_next_gates"].pop("portal_suppression")
    assert evaluate(candidate)["gate"] == "FAIL_REFERENCE_MECHANISM_CONTRACT"
