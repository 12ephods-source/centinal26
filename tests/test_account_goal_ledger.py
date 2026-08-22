import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "automation/account_goals/GOALS.json"
ALLOWED_STATES = {
    "PROPOSED",
    "IMPLEMENTED",
    "TESTED",
    "CI_VERIFIED",
    "INDEPENDENTLY_VERIFIED",
    "SOFTWARE_RELEASE_COMPLETE",
    "DEVICE_TESTED",
    "PERSISTENCE_VERIFIED",
    "DEPLOYED_APP_COMPLETE",
    "PRODUCTION_READY",
    "BLOCKED_EXTERNAL",
    "FAILED",
    "REGRESSED",
    "SUPERSEDED",
}


def load_ledger():
    return json.loads(LEDGER.read_text())


def test_goal_ledger_schema_and_count():
    data = load_ledger()
    assert data["schema"] == "frost-account-goals/v1"
    assert len(data["goals"]) == 30
    assert [g["id"] for g in data["goals"]] == [f"G{i:02d}" for i in range(1, 31)]


def test_goal_states_are_explicit_and_supported():
    data = load_ledger()
    assert set(data["states"]) == ALLOWED_STATES
    for goal in data["goals"]:
        assert goal["state"] in ALLOWED_STATES
        assert goal["name"].strip()
        assert goal["success_criteria"]
        assert all(str(x).strip() for x in goal["success_criteria"])


def test_external_blocking_does_not_equal_success():
    data = load_ledger()
    blocked = [g for g in data["goals"] if g["state"] == "BLOCKED_EXTERNAL"]
    assert blocked
    assert any(g["id"] == "G03" for g in blocked)
    assert "BLOCKED_EXTERNAL" not in {
        "SOFTWARE_RELEASE_COMPLETE",
        "DEPLOYED_APP_COMPLETE",
        "PRODUCTION_READY",
    }


def test_critical_account_invariants_are_represented():
    data = load_ledger()
    names = "\n".join(g["name"] for g in data["goals"])
    for phrase in (
        "Android/Termux",
        "Evidence and provenance",
        "Reusable solution-pattern",
        "OpenQuestRPG",
        "Independent verification",
        "Real economic-value",
        "Human-labor elimination",
        "Self-improving project factory",
    ):
        assert phrase in names
