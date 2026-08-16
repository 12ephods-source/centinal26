from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

from centinal26.export_evidence import ObjectIntegrityError
from centinal26.wordbook import WordbookStore
from centinal26.wordbook_pipeline import discover_latest_export, run_pipeline


def _write_export(path: Path, *, phrase: str = "Proceed. Proceed.") -> None:
    payload = [
        {
            "id": "conversation-1",
            "mapping": {
                "u1": {
                    "message": {
                        "id": "u1",
                        "author": {"role": "user"},
                        "content": {"parts": ["I don't say basically."]},
                    }
                },
                "u2": {
                    "message": {
                        "id": "u2",
                        "author": {"role": "user"},
                        "content": {"parts": [phrase]},
                    }
                },
                "a1": {
                    "message": {
                        "id": "a1",
                        "author": {"role": "assistant"},
                        "content": {"parts": ["Basically this must not become user evidence."]},
                    }
                },
            },
        }
    ]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("conversations.json", json.dumps(payload))
        archive.writestr("user.json", "{}")


def test_pipeline_preserves_before_derivation_and_exports_dictionary(tmp_path: Path) -> None:
    source = tmp_path / "chatgpt-export.zip"
    _write_export(source)
    evidence = tmp_path / "evidence"
    state = tmp_path / "state"
    db = state / "wordbook.sqlite3"

    report = run_pipeline(
        source_file=source,
        evidence_root=evidence,
        database=db,
        state_dir=state,
        message_id="provider-message-1",
        export_id="export-1",
    )

    assert report.preservation_status == "PRESERVED"
    assert len(report.raw_sha256) == 64
    assert Path(report.object_path).is_file()
    assert Path(report.dictionary_path).is_file()
    assert Path(report.evolution_path).is_file()
    assert report.promoted_generations + report.rejected_generations == 100
    assert report.archive_import["archive_sha256"] == report.raw_sha256

    dictionary = json.loads(Path(report.dictionary_path).read_text(encoding="utf-8"))
    words = {entry["word"]: entry["count"] for entry in dictionary["ordinary_words"]}
    meta = {entry["word"]: entry["count"] for entry in dictionary["meta_reference_words"]}
    assert words["proceed"] == 2
    assert "basically" not in words
    assert meta["basically"] == 1

    with WordbookStore(db) as store:
        assert store.query("proceed").ordinary_usage == 2
        assert store.query("basically").ordinary_usage == 0
        assert store.query("basically").meta_reference == 1


def test_pipeline_reprocessing_same_source_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "chatgpt-export.zip"
    _write_export(source)
    evidence = tmp_path / "evidence"
    state = tmp_path / "state"
    db = state / "wordbook.sqlite3"

    first = run_pipeline(
        source_file=source,
        evidence_root=evidence,
        database=db,
        state_dir=state,
        message_id="provider-message-1",
    )
    second = run_pipeline(
        source_file=source,
        evidence_root=evidence,
        database=db,
        state_dir=state,
        message_id="provider-message-1",
    )

    assert first.raw_sha256 == second.raw_sha256
    assert first.receipt_id == second.receipt_id
    assert second.preservation_status == "DUPLICATE_SOURCE"
    assert first.dictionary_sha256 == second.dictionary_sha256
    assert first.evolution_sha256 == second.evolution_sha256

    with WordbookStore(db) as store:
        assert store.query("proceed").ordinary_usage == 2
        archive_count = store.conn.execute(
            "SELECT COUNT(*) FROM wordbook_archive_imports"
        ).fetchone()[0]
        assert archive_count == 1


def test_pipeline_rejects_tampered_canonical_object(tmp_path: Path) -> None:
    source = tmp_path / "chatgpt-export.zip"
    _write_export(source)
    evidence = tmp_path / "evidence"
    state = tmp_path / "state"
    db = state / "wordbook.sqlite3"

    first = run_pipeline(
        source_file=source,
        evidence_root=evidence,
        database=db,
        state_dir=state,
        message_id="provider-message-1",
    )
    object_path = Path(first.object_path)
    object_path.chmod(0o600)
    object_path.write_bytes(b"tampered")

    with pytest.raises(ObjectIntegrityError):
        run_pipeline(
            receipt_id=first.receipt_id,
            evidence_root=evidence,
            database=db,
            state_dir=state,
        )


def test_discover_latest_export_ignores_non_exports(tmp_path: Path) -> None:
    older = tmp_path / "older.zip"
    newer = tmp_path / "newer.zip"
    invalid = tmp_path / "not-chatgpt.zip"
    _write_export(older, phrase="older")
    _write_export(newer, phrase="newer")
    with zipfile.ZipFile(invalid, "w") as archive:
        archive.writestr("something.txt", "no conversations here")

    os.utime(older, ns=(1_000_000_000, 1_000_000_000))
    os.utime(newer, ns=(2_000_000_000, 2_000_000_000))
    os.utime(invalid, ns=(3_000_000_000, 3_000_000_000))

    assert discover_latest_export([tmp_path]) == newer


def test_discover_latest_export_fails_closed_when_absent(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="NO_CHATGPT_EXPORT_ZIP_FOUND"):
        discover_latest_export([tmp_path])
