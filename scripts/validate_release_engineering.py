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
    governance = _load("automation/governance/main_branch_protection.json")
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    chaos = json.loads(Path(args.chaos).read_text(encoding="utf-8"))

    assert release["release_target"] == state["release_target"] == engineering["release_target"]
    assert state["physical_gate"]["issue"] == release["physical_gate"]["tracker_issue"] == 208
    assert engineering["external_gates"]["physical_android_termux"]["tracker_issue"] == 208
    assert engineering["external_gates"]["deployment_authorization"]["tracker_issue"] == 228

    branch_gate = engineering["external_gates"]["branch_protection"]
    assert branch_gate["tracker_issue"] == governance["tracker_issue"] == 271
    assert branch_gate["server_side_readback_required"] is True
    assert branch_gate["workflow_substitution_allowed"] is False
    assert branch_gate["policy"] == "automation/governance/main_branch_protection.json"
    assert branch_gate["controller"] == "scripts/reconcile_main_branch_protection.py"
    assert branch_gate["workflow"] == ".github/workflows/governance-enforcement.yml"
    assert branch_gate["admin_token_secret"] == "FROST_GOVERNANCE_ADMIN_TOKEN"
    assert branch_gate["autonomous_enforcement_when_admin_token_present"] is True
    assert branch_gate["close_tracker_only_after_server_readback"] is True

    assert governance["schema"] == "automation.main_branch_protection_policy/v1"
    assert governance["repository"] == "12ephods-source/centinal26"
    assert governance["branch"] == "main"
    assert governance["required_pull_request"] is True
    assert governance["enforce_admins"] is True
    assert governance["required_status_checks"]["strict"] is True
    assert governance["allow_force_pushes"] is False
    assert governance["allow_deletions"] is False
    assert governance["autonomous_reconciliation"]["server_readback_required"] is True
    assert governance["autonomous_reconciliation"]["workflow_substitution_allowed"] is False
    assert governance["emergency_override"]["ordinary_admin_bypass"] is False
    assert governance["evidence_boundary"]["branch_protection_is_physical_device_evidence"] is False
    assert governance["evidence_boundary"]["branch_protection_is_deployment_authorization"] is False
    required_contexts = set(governance["required_status_checks"]["contexts"])
    assert {
        "baseline",
        "callable-adapter",
        "test (3.11)",
        "test (3.12)",
        "test (3.13)",
        "vertical-slice",
        "host-federation-gate",
        "host-qualification",
        "release-engineering",
        "governance-policy",
    }.issubset(required_contexts)

    assert engineering["external_gates"]["library_cleaner_device_ui"]["tracker_issue"] == 245
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

    print("PASS: release engineering evidence, governance, host chaos, and closeout converge")


if __name__ == "__main__":
    main()
