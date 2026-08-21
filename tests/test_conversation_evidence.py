from __future__ import annotations

from copy import deepcopy

import pytest

from frost_core.conversation_evidence import (
    SECONDARY_RECONCILIATION,
    ConversationEvidenceIngestor,
)
from frost_core.object_store import CanonicalObjectStore


def _state() -> dict:
    return {
        "audit_version": "RF_ACCOUNT_RECONCILE_V2",
        "protocol": {"conversation_id": "conv-001"},
        "conversation_title": "Automation reconciliation",
        "conversation_summary": "Reconciled state",
        "project": {
            "name": "Automation / Centinal26",
            "confidence": 0.91,
            "alternatives": [{"name": "Automation", "confidence": 0.55}],
        },
        "accomplishments": [
            {"item": "host tests passed", "status": "VERIFIED"},
        ],
        "contradictions": [
            {"issue": "old and new state differ", "status": "OPEN"},
        ],
        "persistent_decisions": [
            "event ledger remains authoritative",
        ],
        "reusable_components": [
            {"name": "bundle validator", "status": "VERIFIED_HOST"},
        ],
        "epistemic_caveats": ["device validation is still open"],
    }


def test_ingest_uses_existing_object_store_and_preserves_boundaries(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    ingestor = ConversationEvidenceIngestor(store)

    receipt = ingestor.ingest(
        _state(),
        source_ref="chatgpt:conversation/conv-001",
        file_inventory={
            "files": [
                {
                    "file_name": "artifact.json",
                    "sha256": "a" * 64,
                    "current_status": "VERIFIED_HOST",
                }
            ]
        },
    )

    assert receipt.conversation_id == "conv-001"
    assert receipt.project_candidate_id is not None
    assert len(receipt.claim_ids) == 1
    assert len(receipt.contradiction_ids) == 1
    assert len(receipt.decision_ids) == 1
    assert len(receipt.artifact_ids) == 1
    assert len(receipt.reusable_component_ids) == 1

    provenance = store.provenance(receipt.reconciliation_id)
    assert provenance == [
        {
            "source_type": "chatgpt_reconciliation",
            "source_ref": "chatgpt:conversation/conv-001",
            "evidence_class": SECONDARY_RECONCILIATION,
            "captured_at": provenance[0]["captured_at"],
        }
    ]

    project = store.get(receipt.project_candidate_id)
    assert project.kind == "project_assignment_candidate"
    assert project.payload["status"] == "CANDIDATE"
    assert project.payload["name"] == "Automation / Centinal26"

    contradiction = store.get(receipt.contradiction_ids[0])
    assert contradiction.payload["status"] == "UNRESOLVED"

    reusable = store.get(receipt.reusable_component_ids[0])
    assert reusable.payload["status"] == "CANDIDATE"

    # Reconciliation evidence must not advance a mutable canonical alias.
    with pytest.raises(KeyError):
        store.resolve("project/current")


def test_identical_ingest_is_content_idempotent(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    ingestor = ConversationEvidenceIngestor(store)
    kwargs = {
        "source_ref": "chatgpt:conversation/conv-001",
        "file_inventory": {"files": []},
    }

    first = ingestor.ingest(_state(), **kwargs)
    counts_after_first = store.counts()
    second = ingestor.ingest(_state(), **kwargs)

    assert second == first
    assert store.counts() == counts_after_first


def test_changed_reconciliation_creates_new_root_without_overwriting_old_evidence(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    ingestor = ConversationEvidenceIngestor(store)

    first = ingestor.ingest(_state(), source_ref="chatgpt:conversation/conv-001")
    changed = deepcopy(_state())
    changed["conversation_summary"] = "Reconciled state after additional evidence"
    second = ingestor.ingest(changed, source_ref="chatgpt:conversation/conv-001")

    assert second.reconciliation_id != first.reconciliation_id
    assert store.get(first.reconciliation_id).payload["conversation_summary"] == "Reconciled state"
    assert (
        store.get(second.reconciliation_id).payload["conversation_summary"]
        == "Reconciled state after additional evidence"
    )


def test_missing_evidence_identity_inputs_are_rejected(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    ingestor = ConversationEvidenceIngestor(store)

    with pytest.raises(ValueError, match="source_ref"):
        ingestor.ingest(_state(), source_ref="")

    missing_version = _state()
    missing_version.pop("audit_version")
    with pytest.raises(ValueError, match="audit_version"):
        ingestor.ingest(missing_version, source_ref="chatgpt:conversation/conv-001")

    missing_conversation = _state()
    missing_conversation["protocol"] = {}
    with pytest.raises(ValueError, match="conversation id"):
        ingestor.ingest(missing_conversation, source_ref="chatgpt:conversation/conv-001")
