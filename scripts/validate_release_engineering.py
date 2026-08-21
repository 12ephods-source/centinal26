from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load(relative: str) -> dict[str, Any]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _verify_self_hash(value: dict[str, Any], field: str) -> None:
    claimed = value[field]
    unsigned = dict(value)
    unsigned.pop(field)
    assert hashlib.sha256(_canonical_bytes(unsigned)).hexdigest() == claimed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--chaos", required=True)
    args = parser.parse_args()

    release = _load("releases/RELEASE_CONTRACT.json")
    state = _load("releases/CURRENT_RELEASE_STATE.json")
    engineering = _load("releases/RELEASE_ENGINEERING_CONTRACT.json")
    compatibility = _load("releases/COMPATIBILITY_MATRIX.json")
    deprecation = _load("releases/DEPRECATION_REGISTRY.json")
    rings = _load("releases/RELEASE_RINGS.json")
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    chaos = json.loads(Path(args.chaos).read_text(encoding="utf-8"))

    assert release["release_target"] == state["release_target"] == engineering["release_target"]
    assert state["physical_gate"]["issue"] == release["physical_gate"]["tracker_issue"] == 208
    assert engineering["external_gates"]["physical_android_termux"]["tracker_issue"] == 208
    assert engineering["external_gates"]["deployment_authorization"]["tracker_issue"] == 228
    assert engineering["external_gates"]["branch_protection"]["tracker_issue"] == 271
    assert engineering["external_gates"]["branch_protection"]["workflow_substitution_allowed"] is False
    assert state["adjacent_external_tracks"]["base_ga_blocking"] is False

    assert release["promotion_order"] == [
        "STATIC_VALIDATED",
        "HOST_VALIDATED",
        "DEVICE_VALIDATED",
        "PERSISTENT_VALIDATED",
        "RECOVERY_VALIDATED",
        "GA",
    ]
    assert rings["order"] == ["DEV", "INTERNAL", "DEVICE_CANARY", "FLEET_CANARY", "GA"]
    assert rings["rings"]["DEVICE_CANARY"]["evidence"] == ["DEVICE_VALIDATED"]
    assert rings["rings"]["FLEET_CANARY"]["evidence"] == [
        "PERSISTENT_VALIDATED",
        "RECOVERY_VALIDATED",
    ]
    assert state["current_state"] != "GA"
    assert compatibility["android_termux"]["host_or_emulator_substitution_allowed"] is False
    host_versions = {item["version"]: item["status"] for item in compatibility["host_python"]}
    for version in ("3.11", "3.12", "3.13"):
        assert host_versions[version] == "HOST_CI_REQUIRED"

    allowed_states = set(deprecation["allowed_states"])
    entries = deprecation["entries"]
    assert entries
    assert all(entry["state"] in allowed_states for entry in entries)
    by_id = {entry["id"]: entry for entry in entries}
    assert by_id["physical-contract-issue-64"]["state"] == "SUPERSEDED"
    assert by_id["parallel-live-project-state-authority"]["state"] == "REJECTED"
    assert by_id["direct-ai-to-shell-execution"]["state"] == "REJECTED"

    assert evidence["schema"] == engineering["required_generated_evidence"]["schema"]
    _verify_self_hash(evidence, "manifest_sha256")
    assert len(evidence["source_commit"]) == 40
    assert evidence["source_tree"]["tracked_file_count"] > 0
    assert evidence["source_tree"]["tracked_total_bytes"] > 0
    assert evidence["evidence_boundaries"] == {
        "host_manifest_generated": True,
        "device_validation_inferred": False,
        "persistence_validation_inferred": False,
        "recovery_validation_inferred": False,
        "deployment_authorization_inferred": False,
    }

    tracked = {item["path"]: item for item in evidence["source_tree"]["files"]}
    for path in engineering["required_static_ledgers"]:
        assert path in tracked, path
        assert evidence["canonical_ledgers"][path] == tracked[path]["sha256"]

    python_project = evidence["python_project"]
    assert python_project["name"] == state["runtime_package"]
    if state["current_state"] == "GA":
        assert python_project["version"] == release["release_target"]
    else:
        assert python_project["version"] != release["release_target"]

    recovery = engineering["recovery_semantics"]
    assert recovery["host_recovery_test_does_not_promote_RECOVERY_VALIDATED"] is True
    assert release["recovery_gate"]["promotion"] == "RECOVERY_VALIDATED"

    chaos_contract = engineering["chaos_qualification"]
    assert chaos["schema"] == chaos_contract["schema"]
    assert chaos["scope"] == chaos_contract["scope"] == "HOST_ONLY"
    assert chaos["physical_promotion_allowed"] is False
    assert chaos_contract["physical_promotion_allowed"] is False
    assert chaos["status"] == "PASS"
    _verify_self_hash(chaos, "report_sha256")
    observed_scenarios = [item["scenario"] for item in chaos["scenarios"]]
    assert observed_scenarios == chaos_contract["required_scenarios"]
    assert all(item["status"] == "PASS" for item in chaos["scenarios"])

    print("PASS: release engineering evidence, host chaos, and closeout contracts converge")


if __name__ == "__main__":
    main()
