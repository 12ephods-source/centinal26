import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "automation" / "library_cleaner_state.json"


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8"))


def test_library_cleaner_state_records_qualification_gate() -> None:
    state = load_state()
    assert state["qualification_gate_merge"] == "3da910b9c74b8ca650ee971485304a76679f507c"
    assert state["qualification_gate_exact_head"] == "e499ef8e9a1f7517e6ffc0ccf1f997b64a0fd901"
    assert state["qualification_gate_tests"] == "tests/test_library_cleaner_install_qualification.py"


def test_library_cleaner_installation_remains_fail_closed_before_qualification() -> None:
    state = load_state()
    safety = state["installation_safety"]
    assert safety["initial_auto_delete"] == "FORCED_FALSE"
    assert safety["service_before_qualification"] == "DOWN"
    assert safety["qualification_mode"] == "NON_DESTRUCTIVE_DRY_RUN"
    assert safety["arm_condition"] == "ZERO_REPORTED_ERRORS"
    assert safety["boot_requires_armed_configuration"] is True
    assert safety["local_disarm_control"] is True


def test_host_safety_gate_does_not_promote_physical_ui_state() -> None:
    state = load_state()
    assert state["status"] == "EXPERIMENTAL_HOST_VERIFIED_PHYSICAL_UI_PENDING"
    assert state["promotion_target"] == "VERIFIED"
    assert "do not prove real Android UI execution" in state["boundary"]
