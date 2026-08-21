from __future__ import annotations

import hashlib
import sqlite3

import pytest

from frost_core.object_store import CanonicalObjectStore
from frost_core.second_brain_context import (
    SECOND_BRAIN_V02,
    SecondBrainContextAdapter,
    normalize_second_brain_v02_context,
)


def v02_context() -> dict:
    artifact_bytes = b'{"error":0.001}\n'
    return {
        "generated_utc": "2026-08-21T18:10:00Z",
        "schema_version": "0.2.0",
        "project": {
            "id": "prj-001",
            "title": "Physics Audit Engine",
            "objective": "Build reproducible validation pipelines",
            "status": "Active",
            "epistemic_status": "Partially implemented",
            "provenance_json": '{"created_by":"human"}',
        },
        "decisions": [
            {
                "id": "dec-001",
                "project_id": "prj-001",
                "title": "Preserve evidence",
                "decision_text": "Preserve negative results.",
                "epistemic_status": "Derived",
                "provenance_json": "{}",
            }
        ],
        "experiments": [
            {
                "id": "exp-001",
                "project_id": "prj-001",
                "title": "Convergence sweep",
                "hypothesis": "Error decreases under refinement.",
                "epistemic_status": "Proposed",
                "provenance_json": "{}",
            }
        ],
        "findings": [],
        "security_cases": [],
        "tasks": [],
        "code_modules": [],
        "test_plans": [],
        "library": [
            {
                "id": "lib-001",
                "project_id": "prj-001",
                "title": "Run result",
                "item_type": "Artifact",
                "location": "workspace:///artifacts/run-001.json",
                "checksum_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                "media_type": "application/json",
                "integrity_status": "Verified",
                "epistemic_status": "Verified",
                "provenance_json": '{"source":"register-artifact"}',
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
        "links": [
            {
                "from_type": "experiments",
                "from_id": "exp-001",
                "relation": "derived_run",
                "to_type": "runs",
                "to_id": "run-001",
            }
        ],
    }


def test_v02_context_is_normalized_without_losing_source_records() -> None:
    context = v02_context()
    normalized = normalize_second_brain_v02_context(context)
    assert normalized["source_system"] == SECOND_BRAIN_V02
    assert normalized["export_version"] == "0.2.0-context"
    assert {item["source_id"] for item in normalized["entities"]} == {
        "prj-001",
        "dec-001",
        "exp-001",
        "lib-001",
        "run-001",
    }
    decision = next(item for item in normalized["entities"] if item["source_id"] == "dec-001")
    assert decision["entity_type"] == "decision"
    assert decision["epistemic_status"] == "Derived"
    assert decision["payload"]["record"]["decision_text"] == "Preserve negative results."
    assert len(decision["payload"]["source_record_sha256"]) == 64


def test_v02_context_compiles_into_proposal_only_canonical_object(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = SecondBrainContextAdapter(store)
    proposal = adapter.compile(v02_context())
    assert proposal["status"] == "PROPOSAL_ONLY"
    assert proposal["source_system"] == SECOND_BRAIN_V02
    assert proposal["authority"]["execution_authority"] is False
    assert proposal["authority"]["automatic_epistemic_promotion"] is False
    assert len(proposal["entities"]) == 5
    assert proposal["relationships"] == [
        {
            "source_id": "exp-001",
            "relation": "derived_run",
            "target_id": "run-001",
        }
    ]


def test_v02_identical_reexport_is_idempotent_even_if_generated_time_changes(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = SecondBrainContextAdapter(store)
    first = v02_context()
    second = v02_context()
    second["generated_utc"] = "2026-08-21T19:10:00Z"
    receipt_a = adapter.ingest(first, source_ref="second-brain:context")
    receipt_b = adapter.ingest(second, source_ref="second-brain:context")
    assert receipt_a.proposal_object_id == receipt_b.proposal_object_id
    assert receipt_a.source_digest == receipt_b.source_digest
    with sqlite3.connect(store.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 1


def test_v02_artifact_hash_is_preserved_without_claiming_byte_verification(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    proposal = SecondBrainContextAdapter(store).compile(v02_context())
    artifact = proposal["artifacts"][0]
    assert artifact["artifact_id"] == "lib-001"
    assert artifact["verification"] == "HASH_PRESERVED_BYTES_NOT_PROVIDED"
    assert artifact["logical_ref"] == "workspace:///artifacts/run-001.json"


def test_v02_supplied_artifact_bytes_are_rehashed(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = SecondBrainContextAdapter(store)
    proposal = adapter.compile(
        v02_context(), artifact_payloads={"lib-001": b'{"error":0.001}\n'}
    )
    assert proposal["artifacts"][0]["verification"] == "SHA256_VERIFIED_FROM_SUPPLIED_BYTES"


def test_v02_artifact_mismatch_fails_before_store_write(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = SecondBrainContextAdapter(store)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        adapter.ingest(
            v02_context(),
            source_ref="second-brain:context",
            artifact_payloads={"lib-001": b"wrong"},
        )
    with sqlite3.connect(store.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0


def test_v02_omitted_link_endpoint_fails_instead_of_inventing_record() -> None:
    context = v02_context()
    context["links"][0]["to_id"] = "run-missing"
    with pytest.raises(ValueError, match="endpoint was omitted"):
        normalize_second_brain_v02_context(context)


def test_v02_wrong_schema_version_is_rejected() -> None:
    context = v02_context()
    context["schema_version"] = "0.1.0"
    with pytest.raises(ValueError, match="expected Second Brain schema_version"):
        normalize_second_brain_v02_context(context)


def test_v02_duplicate_ids_across_collections_are_rejected() -> None:
    context = v02_context()
    context["decisions"][0]["id"] = "exp-001"
    with pytest.raises(ValueError, match="duplicate source record IDs"):
        normalize_second_brain_v02_context(context)


def test_v02_source_context_is_not_modified() -> None:
    context = v02_context()
    before = repr(context)
    normalize_second_brain_v02_context(context)
    assert repr(context) == before
