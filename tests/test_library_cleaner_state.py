import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "automation" / "library_cleaner_state.json"
REGISTRY_PATH = ROOT / "automation" / "abilities" / "registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cleaner_ability(registry: dict) -> dict:
    matches = [
        ability
        for ability in registry["abilities"]
        if ability["id"] == "frost-forge/termux-library-cleaner/v1"
    ]
    assert len(matches) == 1
    return matches[0]


def test_library_cleaner_state_matches_ability_registry() -> None:
    state = load_json(STATE_PATH)
    ability = cleaner_ability(load_json(REGISTRY_PATH))

    assert state["status"] == "EXPERIMENTAL_HOST_VERIFIED_PHYSICAL_UI_PENDING"
    assert state["implementation_merge"] == ability["source"]["production_commit"]
    assert state["implementation"] == ability["source"]["path"]
    assert state["installer"] == ability["source"]["installer"]
    assert state["regression_tests"] == ability["verification"]["tests"]
    assert ability["status"] == "EXPERIMENTAL"
    assert ability["verification"]["physical_device_execution"] == "PENDING_PHYSICAL"
    assert ability["verification"]["provider_ui_end_to_end"] == "NOT_YET_OBSERVED"


def test_library_cleaner_promotion_gate_is_explicit() -> None:
    state = load_json(STATE_PATH)

    assert state["qualification_issue"] == 245
    assert state["promotion_target"] == "VERIFIED"
    required = set(state["device_ui_promotion_requirements"])
    assert {
        "authorized_local_adb_pairing",
        "safe_dry_run_candidate_selection",
        "protected_name_rejection",
        "download_before_delete",
        "archive_copy_and_sha256_ledger",
        "authenticated_ui_delete",
        "post_delete_absence_verification",
        "independent_review",
    } <= required
    assert "does not prove real Android UI execution" in state["boundary"]
