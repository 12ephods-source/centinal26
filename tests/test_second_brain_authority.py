from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = ROOT / "automation" / "SECOND_BRAIN_AUTHORITY.json"
PROJECT_STATE_PATH = ROOT / "automation" / "PROJECT_STATE.json"
BLOCKERS_PATH = ROOT / "automation" / "DEFERRED_BLOCKERS.json"

ALLOWED_CLASSIFICATIONS = {"CANONICAL_ALREADY", "PARTIAL", "NEW_REQUIRED"}
ALLOWED_ACTIONS = {
    "REUSE",
    "BUILD_AFTER_INTEGRATION",
    "EXTEND_EXISTING_EXPORTS",
    "HARDEN",
    "EXTEND",
}
EXPECTED_RANKS = set(range(10, 19))
CANONICAL_CONTINUITY_OWNER = "Centinal26 canonical continuity layer"
QUALIFIED_HEAD = "3838b20ce9cbddb9ee5d73432726248dd88398e5"
PRODUCTION_MERGE = "8c07f2f89de638f5d2b4e464250b7cf838d5f070"


def load_authority() -> dict:
    return json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))


def load_project_state() -> dict:
    return json.loads(PROJECT_STATE_PATH.read_text(encoding="utf-8"))


def load_blockers() -> dict:
    return json.loads(BLOCKERS_PATH.read_text(encoding="utf-8"))


def test_authority_map_is_well_formed() -> None:
    data = load_authority()
    assert data["schema"] == "frost.automation.second_brain_authority.v1"
    assert data["version"] == "1.2.0"
    assert data["status"] == "HOST_VERIFIED_EXTERNAL_GATES_PENDING"
    assert data["source_commit"] == PRODUCTION_MERGE
    assert data["authorities"]["repository_and_release_governance"] == "centinal26/main"
    assert data["authorities"]["second_brain_role"].startswith("domain semantics")


def test_machine_continuation_authority_matches_existing_canonical_state() -> None:
    authority = load_authority()
    project_state = load_project_state()
    expected = project_state["source_of_truth"]["machine_continuation"]
    assert expected == "automation/PROJECT_STATE.json"
    assert authority["authorities"]["machine_project_continuation"] == expected


def test_aiccep_is_migration_lineage_not_parallel_live_database_authority() -> None:
    data = load_authority()
    assert "migration/provenance" in data["authorities"]["aiccep_role"]
    assert "not a live canonical database authority" in data["authorities"]["aiccep_role"]
    forbidden = set(data["adapter_contract"]["forbidden"])
    assert "parallel_aiccep_canonical_database_authority" in forbidden
    assert "silent_aiccep_database_rewrite" in forbidden


def test_roadmap_10_through_18_have_unique_entries_and_owners() -> None:
    data = load_authority()
    items = data["roadmap_overlap"]
    ranks = [item["rank"] for item in items]
    assert set(ranks) == EXPECTED_RANKS
    assert len(ranks) == len(set(ranks))
    for item in items:
        assert item["classification"] in ALLOWED_CLASSIFICATIONS
        assert item["action"] in ALLOWED_ACTIONS
        assert item["canonical_owner"].strip()
        assert item["rationale"].strip()


def test_host_qualified_and_partial_roadmap_boundaries_are_explicit() -> None:
    data = load_authority()
    by_rank = {item["rank"]: item for item in data["roadmap_overlap"]}
    assert by_rank[10]["classification"] == "CANONICAL_ALREADY"
    for rank in (12, 13, 14, 15, 16, 18):
        assert by_rank[rank]["classification"] == "CANONICAL_ALREADY"
        assert by_rank[rank]["action"] == "REUSE"
    for rank in (11, 17):
        assert by_rank[rank]["classification"] == "PARTIAL"
        assert by_rank[rank]["action"] == "HARDEN"


def test_second_brain_is_not_a_parallel_runtime_authority() -> None:
    data = load_authority()
    authorities = data["authorities"]
    assert "independent canonical runtime" in authorities["second_brain_role"]
    forbidden = set(data["adapter_contract"]["forbidden"])
    assert "duplicate_artifact_byte_store" in forbidden
    assert "duplicate_execution_runtime" in forbidden


def test_knowledge_and_execution_task_authority_are_separate_without_split_state() -> None:
    data = load_authority()
    entities = data["entity_authority"]
    assert entities["knowledge_task"]["metadata_owner"] == CANONICAL_CONTINUITY_OWNER
    assert entities["execution_task"]["metadata_owner"] == "Centinal26/Frost CORE"
    assert entities["artifact"]["identity_and_bytes_owner"] == "Frost CORE"
    metadata_owners = {
        spec["metadata_owner"]
        for spec in entities.values()
        if "metadata_owner" in spec
        and spec["metadata_owner"] not in {"Git", "Centinal26/Frost CORE"}
    }
    assert metadata_owners == {CANONICAL_CONTINUITY_OWNER}


def test_adapter_is_proposal_only_and_idempotent() -> None:
    data = load_authority()
    contract = data["adapter_contract"]
    required = set(contract["required_properties"])
    assert contract["write_mode"] == "proposal_only"
    assert contract["canonical_target"] == CANONICAL_CONTINUITY_OWNER
    assert "idempotent_reingest" in required
    assert "artifact_hash_verification" in required
    assert "no_implicit_truth_promotion" in required
    assert "no_execution_authorization" in required


def test_exact_host_qualification_is_recorded() -> None:
    verification = load_authority()["verification"]
    assert verification["continuity_hardening_exact_head"] == QUALIFIED_HEAD
    assert verification["continuity_hardening_production_merge"] == PRODUCTION_MERGE
    for key in (
        "ci",
        "automation_validation",
        "validate",
        "automation_gates",
        "federation_gates",
        "mature_product_qualification",
    ):
        assert verification[key] == "PASS"
    assert verification["python_matrix"] == ["3.11", "3.12", "3.13"]


def test_external_and_physical_gates_remain_unpromoted() -> None:
    data = load_authority()
    boundaries = data["external_boundaries"]
    assert boundaries["real_age_encryption"] == "NOT_OBSERVED"
    assert boundaries["off_device_replication_and_restore"] == "NOT_OBSERVED"
    assert boundaries["android_termux_device_validation"] == {
        "status": "PENDING_PHYSICAL",
        "tracker_issue": 208,
    }
    assert boundaries["reboot_persistence"] == {
        "status": "PENDING_PHYSICAL",
        "tracker_issue": 208,
    }
    assert data["promotion_gate"]["current_status"] == (
        "HOST_INTEGRATION_VERIFIED_EXTERNAL_AND_PHYSICAL_GATES_PENDING"
    )


def test_age_off_device_boundary_is_deferred_not_promoted() -> None:
    items = {item["id"]: item for item in load_blockers()["items"]}
    blocker = items["continuity_age_off_device_recovery"]
    assert blocker["status"] == "DEFERRED_BLOCKED"
    assert blocker["evidence"]["host_contract_validation"] == "PASS"
    assert blocker["evidence"]["real_age_end_to_end_evidence"] == "NOT_OBSERVED"
    assert blocker["evidence"]["off_device_replication_evidence"] == "NOT_OBSERVED"
    assert blocker["evidence"]["software_merge"] == "PR #268"
