from __future__ import annotations

import hashlib
import sqlite3

import pytest

from frost_core.continuity_proposal import ContinuityProposalAdapter
from frost_core.object_store import CanonicalObjectStore


def sample_export() -> dict:
    return {
        "source_system": "AICCEP-OS v1.1.0",
        "export_version": "fixture-1",
        "entities": [
            {
                "source_id": "run-1",
                "entity_type": "run",
                "epistemic_status": "DERIVED",
                "revision_parent": None,
                "payload": {"result": "bounded"},
            },
            {
                "source_id": "experiment-1",
                "entity_type": "experiment",
                "epistemic_status": "PROPOSED",
                "revision_parent": None,
                "payload": {"name": "fixture"},
            },
        ],
        "relationships": [
            {
                "source_id": "experiment-1",
                "relation": "HAS_RUN",
                "target_id": "run-1",
            }
        ],
        "artifacts": [],
    }


def test_identical_reingest_is_idempotent(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = ContinuityProposalAdapter(store)

    first = adapter.ingest(sample_export(), source_ref="fixture:aiccep")
    second = adapter.ingest(sample_export(), source_ref="fixture:aiccep")

    assert first == second
    assert store.counts() == {"continuity_migration_proposal": 1}


def test_entity_order_does_not_change_proposal_identity(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = ContinuityProposalAdapter(store)
    original = sample_export()
    reversed_export = {**original, "entities": list(reversed(original["entities"]))}

    first = adapter.ingest(original, source_ref="fixture:a")
    second = adapter.ingest(reversed_export, source_ref="fixture:b")

    assert first.proposal_object_id == second.proposal_object_id
    assert first.source_digest == second.source_digest


def test_epistemic_state_and_relationship_are_preserved(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = ContinuityProposalAdapter(store)
    receipt = adapter.ingest(sample_export(), source_ref="fixture")
    proposal = store.get(receipt.proposal_object_id).payload

    by_source = {item["source_id"]: item for item in proposal["entities"]}
    assert by_source["run-1"]["epistemic_status"] == "DERIVED"
    assert by_source["experiment-1"]["epistemic_status"] == "PROPOSED"
    assert proposal["relationships"] == [
        {
            "source_id": "experiment-1",
            "relation": "HAS_RUN",
            "target_id": "run-1",
        }
    ]


def test_supplied_artifact_bytes_are_hash_verified(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = ContinuityProposalAdapter(store)
    payload = b"immutable historical artifact\n"
    digest = hashlib.sha256(payload).hexdigest()
    export = sample_export()
    export["artifacts"] = [{"artifact_id": "artifact-1", "sha256": digest}]

    receipt = adapter.ingest(
        export,
        source_ref="fixture",
        artifact_payloads={"artifact-1": payload},
    )
    proposal = store.get(receipt.proposal_object_id).payload

    assert proposal["artifacts"][0]["sha256"] == digest
    assert proposal["artifacts"][0]["verification"] == "SHA256_VERIFIED_FROM_SUPPLIED_BYTES"


def test_hash_mismatch_fails_before_any_store_write(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = ContinuityProposalAdapter(store)
    export = sample_export()
    export["artifacts"] = [{"artifact_id": "artifact-1", "sha256": "0" * 64}]

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        adapter.ingest(
            export,
            source_ref="fixture",
            artifact_payloads={"artifact-1": b"different"},
        )

    assert store.counts() == {}


def test_invalid_relationship_fails_before_any_store_write(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = ContinuityProposalAdapter(store)
    export = sample_export()
    export["relationships"] = [
        {"source_id": "experiment-1", "relation": "HAS_RUN", "target_id": "missing"}
    ]

    with pytest.raises(ValueError, match="endpoints must exist"):
        adapter.ingest(export, source_ref="fixture")

    assert store.counts() == {}


def test_duplicate_source_identity_is_rejected(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    adapter = ContinuityProposalAdapter(store)
    export = sample_export()
    export["entities"].append(dict(export["entities"][0]))

    with pytest.raises(ValueError, match="duplicate entity source_id"):
        adapter.ingest(export, source_ref="fixture")

    assert store.counts() == {}


def test_adapter_has_no_alias_or_execution_promotion_side_effect(tmp_path) -> None:
    db_path = tmp_path / "store.sqlite3"
    store = CanonicalObjectStore(db_path)
    adapter = ContinuityProposalAdapter(store)
    receipt = adapter.ingest(sample_export(), source_ref="fixture")
    proposal = store.get(receipt.proposal_object_id).payload

    assert proposal["status"] == "PROPOSAL_ONLY"
    assert proposal["authority"] == {
        "canonical_target": "Centinal26 canonical continuity layer",
        "machine_continuation": "automation/PROJECT_STATE.json",
        "execution_authority": False,
        "automatic_epistemic_promotion": False,
        "automatic_contradiction_resolution": False,
        "alias_or_current_pointer_update": False,
    }
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM aliases").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM alias_history").fetchone()[0] == 0
