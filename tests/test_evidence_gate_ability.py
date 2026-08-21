from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "automation" / "abilities" / "registry.json"
ABILITY_ID = "device/evidence-gate-collector/v1"
QUALIFIED_HEAD = "21a89d0f99f7919a373c7b171043e23bf5a0dc7e"
PRODUCTION_COMMIT = "da78a1c204ccff11c0d77ee18ad2f192db2302ed"


def ability() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    matches = [item for item in registry["abilities"] if item["id"] == ABILITY_ID]
    assert len(matches) == 1
    return matches[0]


def test_evidence_gate_collector_is_registered_with_exact_software_provenance() -> None:
    item = ability()
    assert item["status"] == "VERIFIED"
    assert item["source"]["exact_head"] == QUALIFIED_HEAD
    assert item["source"]["production_commit"] == PRODUCTION_COMMIT
    assert item["verification"]["exact_head"] == QUALIFIED_HEAD
    assert item["verification"]["production_commit"] == PRODUCTION_COMMIT
    for key in (
        "ci",
        "automation_validation",
        "validate",
        "automation_gates",
        "federation_gates",
        "mature_product_qualification",
        "release_engineering_gate",
    ):
        assert item["verification"][key] == "PASS"


def test_registration_preserves_external_and_physical_boundaries() -> None:
    item = ability()
    verification = item["verification"]
    assert verification["physical_device_execution"] == "PENDING_REAL_ANDROID_TERMUX"
    assert verification["real_age_roundtrip"] == "PENDING_REAL_PROVIDER_AND_REMOTE"
    assert verification["independent_judge_verification"] == "PENDING_CONTROLLER_EVIDENCE"
    assert verification["lease_event_chain_verification"] == "PENDING_CONTROLLER_EVIDENCE"
    boundary = item["provenance"]["authority_boundary"]
    assert "no arbitrary shell" in boundary
    assert "remote reboot" in boundary
    assert "automatic DEVICE_VALIDATED/PERSISTENT_VALIDATED promotion" in boundary
