import json
import pathlib
import scripts.ftoe_so10_protected_i_higgs_role_conflict_gate as gate


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "physics/ftoe/protected_I_higgs_role_conflict_v08.json"


def test_frozen_reference_direct_identification_fails() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    result = gate.adjudicate(contract)

    assert result["execution_status"] == "PASS"
    assert result["scientific_verdict"] == gate.EXPECTED_FAIL
    assert all(result["checks"].values())
    assert result["no_retuning"] is True


def test_scope_does_not_claim_extended_coset_no_go() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    result = gate.adjudicate(contract)

    assert "direct identification" in result["scope_limit"]
    assert "does not reject" in result["scope_limit"].lower()
