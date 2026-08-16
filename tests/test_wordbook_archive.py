from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from centinal26.wordbook import WordbookStore
from centinal26.wordbook_archive import ingest_chatgpt_zip, sha256_file


def _payload() -> list[dict[str, object]]:
    return [
        {
            "id": "c1",
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
                        "content": {"parts": ["Proceed."]},
                    }
                },
                "a1": {
                    "message": {
                        "id": "a1",
                        "author": {"role": "assistant"},
                        "content": {"parts": ["Basically, assistant text."]},
                    }
                },
            },
        }
    ]


def _make_zip(path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_zip_import_is_provenanced_and_idempotent(tmp_path: Path) -> None:
    archive = tmp_path / "export.zip"
    conversations = json.dumps(_payload())
    _make_zip(archive, {"conversations.json": conversations, "user.json": "{}"})

    with WordbookStore(tmp_path / "wordbook.sqlite3") as store:
        first = ingest_chatgpt_zip(store, archive)
        assert first.archive_sha256 == sha256_file(archive)
        assert first.conversations_bytes == len(conversations.encode("utf-8"))
        assert first.user_messages == 2
        assert first.non_user_messages == 1
        assert first.ledger_recorded is True
        assert store.query("basically").ordinary_usage == 0
        assert store.query("basically").meta_reference == 1
        assert store.query("proceed").ordinary_usage == 1

        second = ingest_chatgpt_zip(store, archive)
        assert second.ledger_recorded is False
        assert store.query("proceed").ordinary_usage == 1
        ledger_count = store.conn.execute(
            "SELECT COUNT(*) FROM wordbook_archive_imports"
        ).fetchone()[0]
        assert ledger_count == 1


def test_zip_import_rejects_ambiguous_conversations_members(tmp_path: Path) -> None:
    archive = tmp_path / "ambiguous.zip"
    conversations = json.dumps(_payload())
    _make_zip(
        archive,
        {
            "conversations.json": conversations,
            "nested/conversations.json": conversations,
        },
    )
    with WordbookStore() as store, pytest.raises(ValueError, match="exactly one"):
        ingest_chatgpt_zip(store, archive)


def test_zip_import_rejects_traversal_member(tmp_path: Path) -> None:
    archive = tmp_path / "traversal.zip"
    _make_zip(archive, {"../conversations.json": json.dumps(_payload())})
    with WordbookStore() as store, pytest.raises(ValueError, match="unsafe"):
        ingest_chatgpt_zip(store, archive)


def test_zip_import_enforces_member_size_limit(tmp_path: Path) -> None:
    archive = tmp_path / "large.zip"
    _make_zip(archive, {"conversations.json": json.dumps(_payload())})
    with WordbookStore() as store, pytest.raises(ValueError, match="configured limit"):
        ingest_chatgpt_zip(store, archive, max_conversations_bytes=16)


def test_zip_import_rejects_non_zip(tmp_path: Path) -> None:
    archive = tmp_path / "not.zip"
    archive.write_text("not a zip", encoding="utf-8")
    with WordbookStore() as store, pytest.raises(ValueError, match="valid ZIP"):
        ingest_chatgpt_zip(store, archive)
