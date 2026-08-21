import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "automation" / "PROJECT_STATE.json"
HUMAN_PATH = ROOT / "AUTOMATION_OS_RUNTIME_CONSOLIDATION.md"
CONCISE_PATH = ROOT / "PROJECT_STATE_AUTOMATION_OS.md"
PHYSICAL_SOURCE = "9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483"
SUPERSEDED_PHYSICAL_SOURCE = "32ba85c2d0e0a3a704efcc6a7dd93d7e07809d16"


def test_canonical_state_v27_is_synchronized():
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    human = HUMAN_PATH.read_text(encoding="utf-8")
    concise = CONCISE_PATH.read_text(encoding="utf-8")

    assert state["project"]["consolidation_version"] == "2.7"
    assert state["physical_gate"]["qualified_source_commit"] == PHYSICAL_SOURCE
    assert state["project"]["physical_commissioning_source"] == PHYSICAL_SOURCE

    for document in (human, concise):
        assert "2.7" in document
        assert PHYSICAL_SOURCE in document
        assert SUPERSEDED_PHYSICAL_SOURCE not in document


def test_connector_and_automation_truth_is_preserved():
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    connectors = state["connector_qualification"]

    assert connectors["base44"]["status"] == "VERIFIED_LIVE_READ_WRITE"
    assert connectors["notion"]["status"] == "AUTHENTICATED_READ_VERIFIED"
    assert connectors["linear"]["status"] == "AUTHENTICATED_READ_VERIFIED"
    assert (
        state["automation_topology"]["duplicate_physical_watch"]["status"]
        == "PAUSED_SUPERSEDED"
    )


def test_device_profile_remains_evidence_context_not_authority():
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    profile = state["physical_gate"]["user_supplied_device_context"]

    assert profile["model"] == "SM-A155M"
    assert profile["android_version"] == "16"
    assert profile["architecture"] == "aarch64"
    assert profile["status"] == "USER_SUPPLIED_UNVERIFIED_UNTIL_DEVICE_BUNDLE"
    assert "authorization" in profile["use"]
