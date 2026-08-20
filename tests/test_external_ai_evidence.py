from __future__ import annotations

import hashlib

import pytest

from frost_core.external_ai_evidence import (
    EXTERNAL_AI_LOCATOR,
    EXTERNAL_AI_PRIMARY_SOURCE,
    ExternalAIEvidenceIngestor,
)
from frost_core.object_store import CanonicalObjectStore


def test_unavailable_shared_link_records_locator_only(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    ingestor = ExternalAIEvidenceIngestor(store)

    receipt = ingestor.ingest(
        platform="gemini",
        source_ref="https://share.gemini.google/example",
        acquisition_status="UNAVAILABLE",
        completeness="UNKNOWN",
    )

    assert receipt.transcript_id is None
    assert receipt.analysis_ready is False
    assert store.counts() == {"external_ai_source": 1}
    assert store.provenance(receipt.source_id)[0]["evidence_class"] == EXTERNAL_AI_LOCATOR
    with pytest.raises(KeyError):
        store.resolve("project/current")


def test_acquired_transcript_requires_matching_hash_and_preserves_source(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    ingestor = ExternalAIEvidenceIngestor(store)
    text = "user: hello\nassistant: hello"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

    receipt = ingestor.ingest(
        platform="gemini",
        source_ref="gemini:conversation/example",
        conversation_id="example",
        acquisition_status="ACQUIRED",
        completeness="COMPLETE",
        transcript_text=text,
        transcript_sha256=digest,
        attachments=[{"name": "figure.png", "status": "PRESENT"}],
    )

    assert receipt.analysis_ready is True
    assert receipt.transcript_id is not None
    transcript = store.get(receipt.transcript_id)
    assert transcript.kind == "external_ai_transcript"
    assert transcript.payload["text"] == text
    assert transcript.payload["sha256"] == digest
    provenance = store.provenance(receipt.transcript_id)
    assert provenance[0]["evidence_class"] == EXTERNAL_AI_PRIMARY_SOURCE
    assert provenance[0]["source_type"] == "external_ai:gemini"
    with pytest.raises(KeyError):
        store.resolve("project/current")


def test_hash_mismatch_is_rejected(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    ingestor = ExternalAIEvidenceIngestor(store)

    with pytest.raises(ValueError, match="does not match"):
        ingestor.ingest(
            platform="claude",
            source_ref="claude:conversation/example",
            acquisition_status="ACQUIRED",
            completeness="COMPLETE",
            transcript_text="actual",
            transcript_sha256="0" * 64,
        )


def test_partial_source_must_be_explicitly_partial(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    ingestor = ExternalAIEvidenceIngestor(store)
    text = "partial transcript"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

    with pytest.raises(ValueError, match="PARTIAL source completeness"):
        ingestor.ingest(
            platform="copilot",
            source_ref="copilot:conversation/example",
            acquisition_status="PARTIAL",
            completeness="COMPLETE",
            transcript_text=text,
            transcript_sha256=digest,
        )


def test_identical_ingest_is_content_addressed_and_idempotent(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    ingestor = ExternalAIEvidenceIngestor(store)
    text = "stable transcript"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    args = {
        "platform": "gemini",
        "source_ref": "gemini:conversation/stable",
        "acquisition_status": "ACQUIRED",
        "completeness": "COMPLETE",
        "transcript_text": text,
        "transcript_sha256": digest,
    }

    first = ingestor.ingest(**args)
    second = ingestor.ingest(**args)

    assert first == second
    assert store.counts() == {
        "external_ai_source": 1,
        "external_ai_transcript": 1,
    }
