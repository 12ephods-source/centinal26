import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "releases/1.0.0-rc4-converged/PARENT_INPUTS.json"
SCRIPT = ROOT / "deploy/termux/recover-rc4-parent-inputs.sh"

SCHEMA10_SHA = "e21ed868d11ec7525a0fba54e58854b00a9fd151681a1efc26ffd9cf202f40d2"
SCHEMA10_PAYLOAD_SHA = "79e53364ff0462dadf9b1d454123791c0db26d0a860bda98cf3e788183106e0a"
GA_SHA = "cfd2e3e285550b2d4f995a7edf10377ca983276da9b79e16084e0a36b040e7d7"
GA_PAYLOAD_SHA = "692c59e891d5f539933c363563b1256b10c225d15878598724b9b6cca03c8f58"


def test_parent_input_metadata_is_pinned_and_unimported():
    data = json.loads(INPUTS.read_text(encoding="utf-8"))
    assert data["target_release"] == "1.0.0-rc4-converged"
    assert data["minimum_schema_version"] == 10
    assert data["content_imported"] is False
    assert data["transport_state"] == "EXACT_BYTES_LOCATED_IN_FILE_LIBRARY_NOT_MOUNTED"

    schema10 = data["parents"]["schema10_device_validation"]
    assert schema10["file_library_ref"] == "file_000000005ff881fda332f1e5ec79ca22"
    assert schema10["sha256"] == SCHEMA10_SHA
    assert schema10["embedded_payload_sha256"] == SCHEMA10_PAYLOAD_SHA
    assert schema10["size_bytes"] == 844877
    assert schema10["repository_bytes_present"] is False

    ga = data["parents"]["schema9_ga_campaign"]
    assert ga["file_library_ref"] == "file_000000005cd881fd9404a97fa7c7c32c"
    assert ga["sha256"] == GA_SHA
    assert ga["embedded_payload_sha256"] == GA_PAYLOAD_SHA
    assert ga["size_bytes"] == 278935
    assert ga["repository_bytes_present"] is False


def test_recovery_script_is_hash_bound_and_non_executing():
    text = SCRIPT.read_text(encoding="utf-8")
    for marker in [SCHEMA10_SHA, SCHEMA10_PAYLOAD_SHA, GA_SHA, GA_PAYLOAD_SHA]:
        assert marker in text
    for marker in [
        "find_exact_hash",
        "select_exact",
        "extract_payload",
        '"installers_executed": False',
        '"semantic_convergence_reviewed": False',
        '"physical_android_validated": False',
        '"promotion_performed": False',
    ]:
        assert marker in text
    assert 'bash "$SCHEMA10' not in text
    assert 'bash "$GA_' not in text
    assert 'source "$SCHEMA10' not in text
    assert 'source "$GA_' not in text


def test_recovery_metadata_does_not_advance_release_gates():
    state = json.loads((ROOT / "releases/BOOTSTRAP_STATE.json").read_text(encoding="utf-8"))
    gates = state["gates"]
    for gate in [
        "rc4_semantic_branch_convergence_reviewed",
        "rc4_candidate_constructed",
        "rc4_host_qualified",
        "android_device_validated",
        "endurance_validated",
        "device_sync_validated",
        "recovery_drill_validated",
        "native_candidate_certified",
        "explicit_human_promotion",
    ]:
        assert gates[gate] is False
