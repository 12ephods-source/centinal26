from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from centinal26.export_evidence import (
    ObjectIntegrityError,
    SourceIdentityConflict,
    preserve_export,
    verify_receipt,
)


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_preserves_exact_raw_bytes_and_receipt(tmp_path: Path) -> None:
    source = _write(tmp_path / "chatgpt-export.zip", b"raw-export-bytes")
    root = tmp_path / "store"
    result = preserve_export(
        source,
        provider="openai-chatgpt",
        root=root,
        message_id="gmail-message-1",
        export_id="export-1",
        message_date="2026-08-16T10:00:00Z",
        subject="ChatGPT - Your data export is ready",
        retrieved_at="2026-08-16T10:01:00Z",
    )

    assert result.status == "PRESERVED"
    assert Path(result.object_path).read_bytes() == b"raw-export-bytes"
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert receipt["provider"] == "openai-chatgpt"
    assert receipt["source_identity"]["message_id"] == "gmail-message-1"
    assert receipt["source_identity"]["export_id"] == "export-1"
    assert receipt["content"]["raw_preserved_unextracted"] is True
    assert receipt["content"]["sha256"] == result.sha256
    assert verify_receipt(root, result.receipt_id).status == "VERIFIED"


def test_same_source_and_bytes_is_idempotent(tmp_path: Path) -> None:
    source = _write(tmp_path / "export.zip", b"same")
    root = tmp_path / "store"
    first = preserve_export(source, provider="openai", root=root, message_id="m1")
    second = preserve_export(source, provider="openai", root=root, message_id="m1")

    assert first.status == "PRESERVED"
    assert second.status == "DUPLICATE_SOURCE"
    assert first.receipt_id == second.receipt_id
    assert len(list((root / "receipts").glob("*.json"))) == 1


def test_different_source_same_bytes_reuses_content_object(tmp_path: Path) -> None:
    one = _write(tmp_path / "one.zip", b"identical")
    two = _write(tmp_path / "two.zip", b"identical")
    root = tmp_path / "store"
    first = preserve_export(one, provider="openai", root=root, message_id="m1")
    second = preserve_export(two, provider="openai", root=root, message_id="m2")

    assert first.status == "PRESERVED"
    assert second.status == "REUSED_OBJECT"
    assert first.object_path == second.object_path
    assert first.receipt_id != second.receipt_id
    assert len(list((root / "receipts").glob("*.json"))) == 2


def test_same_provider_message_cannot_rebind_to_different_bytes(tmp_path: Path) -> None:
    one = _write(tmp_path / "one.zip", b"first")
    two = _write(tmp_path / "two.zip", b"second")
    root = tmp_path / "store"
    preserve_export(one, provider="openai", root=root, message_id="m1")

    with pytest.raises(SourceIdentityConflict, match="SOURCE_IDENTITY_CONFLICT"):
        preserve_export(two, provider="openai", root=root, message_id="m1")


def test_same_provider_export_id_cannot_rebind_to_different_bytes(tmp_path: Path) -> None:
    one = _write(tmp_path / "one.zip", b"first")
    two = _write(tmp_path / "two.zip", b"second")
    root = tmp_path / "store"
    preserve_export(one, provider="openai", root=root, export_id="e1")

    with pytest.raises(SourceIdentityConflict, match="SOURCE_IDENTITY_CONFLICT"):
        preserve_export(two, provider="openai", root=root, export_id="e1")


def test_zip_is_not_extracted_during_preservation(tmp_path: Path) -> None:
    source = tmp_path / "chatgpt-export.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("conversations.json", '[{"title":"example"}]')
    root = tmp_path / "store"
    result = preserve_export(source, provider="openai", root=root, message_id="m1")

    assert Path(result.object_path).is_file()
    assert not list(root.rglob("conversations.json"))


def test_tampered_object_fails_verification_and_reuse(tmp_path: Path) -> None:
    source = _write(tmp_path / "export.zip", b"evidence")
    root = tmp_path / "store"
    result = preserve_export(source, provider="openai", root=root, message_id="m1")
    object_path = Path(result.object_path)
    object_path.chmod(0o600)
    object_path.write_bytes(b"tampered")

    with pytest.raises(ObjectIntegrityError, match="OBJECT_INTEGRITY_FAILURE"):
        verify_receipt(root, result.receipt_id)
    with pytest.raises(ObjectIntegrityError, match="OBJECT_INTEGRITY_FAILURE"):
        preserve_export(source, provider="openai", root=root, message_id="m1")


def test_index_is_append_only_per_new_receipt(tmp_path: Path) -> None:
    source = _write(tmp_path / "export.zip", b"evidence")
    root = tmp_path / "store"
    preserve_export(source, provider="openai", root=root, message_id="m1")
    preserve_export(source, provider="openai", root=root, message_id="m1")
    preserve_export(source, provider="openai", root=root, message_id="m2")

    lines = (root / "index" / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["schema"].endswith("/v1") for line in lines)
