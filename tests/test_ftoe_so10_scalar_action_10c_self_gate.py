import json
from pathlib import Path

from scripts import ftoe_so10_scalar_action_10c_self_gate as gate


def load_contract() -> dict:
    path = Path("physics/ftoe/scalar_action_10c_self_v13.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_frozen_10c_self_sector_passes() -> None:
    result = gate.evaluate(load_contract())
    assert result["execution_pass"] is True
    assert result["claim_status"] == "PARTIAL_ACTION_10_C_H_SELF_SECTOR_SOURCE_ENUMERATED"
    assert result["scientific_status"] == "REVIEW"
    assert result["full_action_gate"] == "NOT_COMPLETE"


def test_missing_complex_quartic_fails() -> None:
    contract = load_contract()
    contract["self_sector"]["complex_quartic_invariants"] = []
    result = gate.evaluate(contract)
    assert result["execution_pass"] is False
    assert result["checks"]["complex_quartic_basis"] is False


def test_false_full_action_claim_fails() -> None:
    contract = load_contract()
    contract["full_action_gate"] = "COMPLETE"
    result = gate.evaluate(contract)
    assert result["execution_pass"] is False
    assert result["checks"]["full_action_fail_closed"] is False
