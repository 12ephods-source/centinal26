import hashlib
import json

import pytest

from centinal26.second_brain_adapter import (
    PROPOSAL_SCHEMA,
    ProposalConflict,
    ProposalIndex,
    SecondBrainProposalError,
    build_proposal_bundle,
    verify_proposal_bundle,
)


def sample_export() -> dict:
    return {
        "generated_utc": "2026-08-21T18:10:00Z",
        "schema_version": "0.2.0",
        "project": {
            "id": "prj-001",
            "title": "Physics Audit Engine",
            "objective": "Reproducible validation",
            "status": "Active",
            "epistemic_status": "Partially implemented",
            "provenance_json": json.dumps({"created_by": "human", "source_ref": "chat"}),
        },
        "decisions": [
            {
                "id": "dec-001",
                "project_id": "prj-001",
                "title": "Preserve negative results",
                "decision_text": "Negative results remain in history.",
                "epistemic_status": "Derived",
                "provenance_json": {"created_by": "human"},
            }
        ],
        "experiments": [
            {
                "id": "exp-001",
                "project_id": "prj-001",
                "title": "Convergence sweep",
                "hypothesis": "Smaller tolerance reduces error.",
                "epistemic_status": "Proposed",
                "provenance_json": "{}",
            }
        ],
        "runs": [
            {
                "id": "run-001",
                "experiment_id": "exp-001",
                "status": "Completed",
                "parameters_json": '{"tolerance":0.01}',
                "metrics_json": '{"error":0.001}',
                "validation_verdict": "PASS",
                "epistemic_status": "Reported",
                "provenance_json": '{"created_by":"automation"}',
            }
        ],
        "findings": [],
        "security_cases": [],
        "tasks": [
            {
                "id": "tsk-001",
                "project_id": "prj-001",
                "title": "Replicate convergence sweep",
                "status": "Next",
                "epistemic_status": "Proposed",
                "provenance_json": "{}",
            }
        ],
        "code_modules": [],
        "test_plans": [],
        "library": [
            {
                "id": "lib-001",
                "project_id": "prj-001",
                "title": "Run output",
                "item_type": "Artifact",
                "location": "workspace:///artifacts/run-001.json",
                "checksum_sha256": hashlib.sha256(b"artifact-bytes").hexdigest(),
                "epistemic_status": "Verified",
                "provenance_json": '{"source":"register-artifact"}',
            }
        ],
        "links": [
            {
                "from_type": "experiments",
                "from_id": "exp-001",
                "relation": "has_run",
                "to_type": "runs",
                "to_id": "run-001",
            }
        ],
    }


def proposal_by_source_id(bundle: dict, source_id: str) -> dict:
    return next(item for item in bundle["records"] if item["source_id"] == source_id)


def test_actual_v02_export_shape_converts_to_proposal_only_bundle() -> None:
    export = sample_export()
    bundle = build_proposal_bundle(export)
    assert bundle["schema"] == PROPOSAL_SCHEMA
    assert bundle["source_schema_version"] == "0.2.0"
    assert bundle["authority"] == "proposal_only"
    assert bundle["execution_authorized"] is False
    assert bundle["truth_promoted"] is False
    assert bundle["record_count"] == 6
    assert bundle["relationship_count"] == 1
    assert verify_proposal_bundle(bundle)


def test_conversion_is_deterministic_for_identical_export() -> None:
    export = sample_export()
    first = build_proposal_bundle(export)
    second = build_proposal_bundle(export)
    assert first == second
    assert first["bundle_sha256"] == second["bundle_sha256"]


def test_source_ids_epistemic_status_and_provenance_are_preserved() -> None:
    bundle = build_proposal_bundle(sample_export())
    decision = proposal_by_source_id(bundle, "dec-001")
    assert decision["source_id"] == "dec-001"
    assert decision["epistemic_status"] == "Derived"
    assert decision["provenance"] == {"created_by": "human"}
    assert decision["record"]["decision_text"] == "Negative results remain in history."
    assert len(decision["source_record_sha256"]) == 64


def test_experiment_run_relationship_is_preserved() -> None:
    bundle = build_proposal_bundle(sample_export(), strict_relationships=True)
    relationship = bundle["relationships"][0]
    assert relationship["from_id"] == "exp-001"
    assert relationship["relation"] == "has_run"
    assert relationship["to_id"] == "run-001"
    assert relationship["endpoint_status"] == "RESOLVED_IN_EXPORT"
    assert relationship["authority"] == "proposal_only"


def test_unresolved_relationship_is_explicit_not_silently_repaired() -> None:
    export = sample_export()
    export["links"][0]["to_id"] = "run-missing"
    bundle = build_proposal_bundle(export)
    relationship = bundle["relationships"][0]
    assert relationship["endpoint_status"] == "UNRESOLVED_EXTERNAL"
    assert relationship["missing_source_ids"] == ["run-missing"]


def test_strict_relationship_mode_rejects_missing_endpoint() -> None:
    export = sample_export()
    export["links"][0]["to_id"] = "run-missing"
    with pytest.raises(SecondBrainProposalError, match="absent from export"):
        build_proposal_bundle(export, strict_relationships=True)


def test_artifact_declared_hash_can_be_independently_verified() -> None:
    expected = hashlib.sha256(b"artifact-bytes").hexdigest()
    bundle = build_proposal_bundle(sample_export(), artifact_hashes={"lib-001": expected})
    artifact = proposal_by_source_id(bundle, "lib-001")
    assert artifact["artifact_integrity"] == {
        "declared_sha256": expected,
        "observed_sha256": expected,
        "status": "VERIFIED_MATCH",
    }


def test_unavailable_artifact_bytes_remain_declared_unverified() -> None:
    bundle = build_proposal_bundle(sample_export())
    artifact = proposal_by_source_id(bundle, "lib-001")
    assert artifact["artifact_integrity"]["status"] == "DECLARED_UNVERIFIED"


def test_artifact_hash_mismatch_fails_closed() -> None:
    wrong = hashlib.sha256(b"wrong").hexdigest()
    with pytest.raises(SecondBrainProposalError, match="artifact checksum mismatch"):
        build_proposal_bundle(sample_export(), artifact_hashes={"lib-001": wrong})


def test_idempotent_reingest_produces_duplicates_not_new_objects() -> None:
    bundle = build_proposal_bundle(sample_export())
    index = ProposalIndex()
    first = index.ingest(bundle)
    second = index.ingest(bundle)
    assert first["new_records"] == bundle["record_count"]
    assert first["new_relationships"] == bundle["relationship_count"]
    assert second["new_records"] == 0
    assert second["duplicate_records"] == bundle["record_count"]
    assert second["new_relationships"] == 0
    assert second["duplicate_relationships"] == bundle["relationship_count"]
    assert second["execution_authorized"] is False
    assert second["truth_promoted"] is False


def test_changed_content_under_same_source_identity_conflicts_atomically() -> None:
    export = sample_export()
    index = ProposalIndex()
    index.ingest(build_proposal_bundle(export))
    previous_records = dict(index.records)
    previous_relationships = dict(index.relationships)

    changed = sample_export()
    changed["decisions"][0]["decision_text"] = "Changed immutable source content"
    with pytest.raises(ProposalConflict, match="changed content"):
        index.ingest(build_proposal_bundle(changed))

    assert index.records == previous_records
    assert index.relationships == previous_relationships


def test_bundle_tampering_is_detected_before_ingest() -> None:
    bundle = build_proposal_bundle(sample_export())
    bundle["records"][0]["record"]["title"] = "tampered"
    assert verify_proposal_bundle(bundle) is False
    with pytest.raises(SecondBrainProposalError, match="hash verification failed"):
        ProposalIndex().ingest(bundle)


def test_optional_second_brain_entities_and_revision_lineage_are_preserved() -> None:
    export = sample_export()
    export["theory"] = [
        {
            "id": "thy-001",
            "title": "Convergence claim",
            "statement": "The solver converges.",
            "epistemic_status": "Derived",
            "provenance_json": "{}",
        }
    ]
    export["evidence"] = [
        {
            "id": "evd-001",
            "title": "Numerical evidence",
            "claim_id": "thy-001",
            "epistemic_status": "Verified",
            "provenance_json": "{}",
        }
    ]
    export["revisions"] = [
        {
            "id": "rev-001",
            "entity_id": "thy-001",
            "revision_number": 2,
            "action": "edit",
            "before_json": '{"statement":"candidate"}',
            "after_json": '{"statement":"The solver converges."}',
            "epistemic_status": "Reported",
            "provenance_json": "{}",
        }
    ]
    bundle = build_proposal_bundle(export)
    assert proposal_by_source_id(bundle, "thy-001")["entity_type"] == "theory_claim"
    assert proposal_by_source_id(bundle, "evd-001")["entity_type"] == "evidence"
    revision = proposal_by_source_id(bundle, "rev-001")
    assert revision["entity_type"] == "knowledge_revision"
    assert revision["record"]["revision_number"] == 2


def test_duplicate_source_id_within_same_entity_type_is_rejected() -> None:
    export = sample_export()
    export["decisions"].append(dict(export["decisions"][0]))
    with pytest.raises(ProposalConflict, match="duplicate stable proposal identity"):
        build_proposal_bundle(export)


def test_source_export_is_not_mutated() -> None:
    export = sample_export()
    before = json.loads(json.dumps(export))
    build_proposal_bundle(export)
    assert export == before
