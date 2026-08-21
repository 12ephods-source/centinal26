#!/usr/bin/env python3
"""Fail-closed validation for canonical Automation release/authority convergence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def main() -> None:
    project = load("automation/PROJECT_STATE.json")
    release = load("releases/CURRENT_RELEASE_STATE.json")
    contract = load("releases/RELEASE_CONTRACT.json")
    authority = load("releases/AUTHORITY_MATRIX.json")

    # There is one current physical-gate identity everywhere.
    assert project["external_gate_trackers"]["physical_android_termux"] == 208
    assert project["physical_gate"]["tracker_issue"] == 208
    assert release["physical_gate"]["issue"] == 208
    assert contract["physical_gate"]["tracker_issue"] == 208

    # The old issue remains provenance only and cannot regain release authority.
    assert project["physical_gate"]["legacy_paths"]["issue_64"] == "SUPERSEDED_FOR_CURRENT_PHYSICAL_ACCEPTANCE"
    assert release["historical_physical_contracts"]["issue_64"]["status"] == "SUPERSEDED_FOR_CURRENT_PHYSICAL_ACCEPTANCE"
    superseded = {item["issue"]: item["status"] for item in contract["superseded_physical_contracts"]}
    assert superseded[64] == "HISTORICAL_PROVENANCE_ONLY"

    # Machine state, release mirror, release contract, and authority map are explicit.
    assert release["canonical_project_state"] == "automation/PROJECT_STATE.json"
    assert release["release_contract"] == "releases/RELEASE_CONTRACT.json"
    assert release["authority_matrix"] == "releases/AUTHORITY_MATRIX.json"
    assert contract["canonical_state"] == "automation/PROJECT_STATE.json"
    assert contract["release_state_mirror"] == "releases/CURRENT_RELEASE_STATE.json"
    assert contract["authority_matrix"] == "releases/AUTHORITY_MATRIX.json"

    # Promotion is ordered and host evidence cannot substitute for physical evidence.
    assert contract["promotion_order"] == [
        "STATIC_VALIDATED",
        "HOST_VALIDATED",
        "DEVICE_VALIDATED",
        "PERSISTENT_VALIDATED",
        "RECOVERY_VALIDATED",
        "GA",
    ]
    non_substitution = set(contract["evidence_non_substitution"])
    assert "HOST_VALIDATED != DEVICE_VALIDATED" in non_substitution
    assert "DEVICE_VALIDATED != PERSISTENT_VALIDATED" in non_substitution
    assert "EXECUTED != VERIFIED" in non_substitution

    required_checks = set(contract["mandatory_host_checks"])
    assert required_checks == {
        "validate",
        "CI",
        "automation-gates",
        "federation-gates",
        "Mature Product Qualification",
    }
    assert set(release["required_host_checks"]) == required_checks

    # Each authority domain has exactly one canonical writer path.
    domains = authority["domains"]
    required_domains = {
        "project_state",
        "artifact_identity",
        "authorization",
        "execution",
        "verification",
        "evidence_and_audit",
        "release_promotion",
    }
    assert set(domains) == required_domains
    for name, spec in domains.items():
        assert isinstance(spec["authority"], str) and spec["authority"].strip(), name
        assert isinstance(spec["writers"], list) and len(spec["writers"]) == 1, name
        assert isinstance(spec["forbidden"], list) and spec["forbidden"], name

    # Adjacent qualification tracks do not silently become base-GA substitutes.
    assert release["adjacent_external_tracks"]["base_ga_blocking"] is False
    assert contract["non_blocking_adjacent_tracks"] == {
        "connector_qualification_issue": 209,
        "deployment_issue": 228,
        "library_cleaner_issue": 245,
        "bluetooth_issue": 261,
    }

    print("PASS: release state, physical gate, and authority ownership converge on one canonical contract")


if __name__ == "__main__":
    main()
