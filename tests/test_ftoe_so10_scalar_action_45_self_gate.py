import json
from pathlib import Path

from scripts import ftoe_so10_scalar_action_45_self_gate as gate


def load_contract() -> dict:
    path = Path("physics/ftoe/scalar_action_45_self_v11.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_frozen_45_self_sector_passes() -> None:
    result = gate.evaluate(load_contract())
    assert result["execution_pass"] is True
    assert result["claim_status"] == "PARTIAL_ACTION_45_SELF_SECTOR_SOURCE_ENUMERATED"
    assert result["scientific_status"] == "REVIEW"
    assert result["full_action_gate"] == "NOT_COMPLETE"


def test_missing_independent_quartic_fails() -> None:
    contract = load_contract()
    contract["self_sector"]["quartic_invariants"] = ["(Tr(Phi^2))^2"]
    contract["self_sector"]["independent_quartic_count"] = 1
    result = gate.evaluate(contract)
    assert result["execution_pass"] is False
    assert result["checks"]["quartic_basis"] is False
    assert result["checks"]["quartic_count"] is False


def test_cubic_self_interaction_is_rejected() -> None:
    contract = load_contract()
    contract["self_sector"]["cubic_invariants"] = ["Tr(Phi^3)"]
    result = gate.evaluate(contract)
    assert result["execution_pass"] is False
    assert result["checks"]["cubic_absent"] is False


def test_full_action_cannot_be_promoted_here() -> None:
    contract = load_contract()
    contract["full_action_gate"] = "COMPLETE"
    result = gate.evaluate(contract)
    assert result["execution_pass"] is False
    assert result["checks"]["full_action_fail_closed"] is False
