from __future__ import annotations

import json
import stat
import zipfile
from pathlib import Path

from frost_core.export_recovery import (
    build_multipart_manifest,
    chatgpt_filename_from_signed_url,
    download_chatgpt_signed_export,
    google_auth_blocked,
    ingest_takeout_parts,
    inspect_archive,
    preserve_raw_archive,
)


def _zip(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return path


def test_preserve_raw_is_content_addressed_and_read_only(tmp_path: Path) -> None:
    source = _zip(tmp_path / "takeout-001.zip", {"Takeout/a.txt": "a"})
    root = tmp_path / "evidence"
    first = preserve_raw_archive(source, root)
    second = preserve_raw_archive(source, root)
    assert first.sha256 == second.sha256
    assert first.deduplicated is False
    assert second.deduplicated is True
    mode = Path(first.storage_path).stat().st_mode
    assert not mode & stat.S_IWUSR


def test_takeout_provider_omission_forces_incomplete(tmp_path: Path) -> None:
    part = _zip(
        tmp_path / "takeout-001.zip",
        {"Takeout/archive_browser.html": "<html>errors</html>"},
    )
    bundle = ingest_takeout_parts(
        request_id="req-1",
        part_paths=[part],
        evidence_root=tmp_path / "evidence",
        expected_parts=["takeout-001.zip"],
        provider_reports_omissions=True,
    )
    assert bundle.status == "EXPORT_INCOMPLETE"
    manifest = bundle.diagnostics["manifest"]
    assert manifest["provider_complete"] is False
    assert bundle.evidence[-1]["observation_class"] == "DERIVED"
    assert bundle.evidence[-1]["provider_completeness"] == "INCOMPLETE"
    assert bundle.evidence[0]["immutable_raw"] is True


def test_missing_multipart_part_forces_incomplete(tmp_path: Path) -> None:
    part = _zip(tmp_path / "takeout-001.zip", {"Takeout/a.txt": "a"})
    raw = preserve_raw_archive(part, tmp_path / "evidence")
    manifest = build_multipart_manifest(
        [raw], expected_parts=["takeout-001.zip", "takeout-002.zip"]
    )
    assert manifest.missing_parts == ("takeout-002.zip",)
    assert manifest.provider_complete is False


def test_complete_takeout_requires_declared_complete_part_set(tmp_path: Path) -> None:
    p1 = _zip(tmp_path / "takeout-001.zip", {"Takeout/a.txt": "a"})
    p2 = _zip(tmp_path / "takeout-002.zip", {"Takeout/b.txt": "b"})
    bundle = ingest_takeout_parts(
        request_id="req-2",
        part_paths=[p2, p1],
        evidence_root=tmp_path / "evidence",
        expected_parts=["takeout-001.zip", "takeout-002.zip"],
        provider_reports_omissions=False,
    )
    assert bundle.status == "EXPORT_ACQUIRED"
    assert bundle.evidence[-1]["provider_completeness"] == "COMPLETE"


def test_archive_inspection_finds_error_metadata(tmp_path: Path) -> None:
    archive = _zip(
        tmp_path / "takeout.zip",
        {
            "Takeout/archive_browser.html": "ok",
            "Takeout/provider-errors.html": "missing",
        },
    )
    result = inspect_archive(archive)
    assert result.integrity_pass is True
    assert result.archive_browser_html == ("Takeout/archive_browser.html",)
    assert result.error_html == ("Takeout/provider-errors.html",)


def test_chatgpt_url_is_never_serialized_on_failed_fetch(tmp_path: Path) -> None:
    signed = (
        "https://chatgpt.com/backend-api/estuary/content?"
        "id=export-20260817.zip&sig=SUPERSECRET&ts=123"
    )
    assert chatgpt_filename_from_signed_url(signed) == "export-20260817.zip"
    bundle = download_chatgpt_signed_export(
        signed_url=signed,
        source_identity="gmail:message-1",
        evidence_root=tmp_path / "evidence",
        timeout_seconds=0.001,
    )
    serialized = bundle.to_json()
    assert "SUPERSECRET" not in serialized
    assert "https://chatgpt.com" not in serialized
    assert json.loads(serialized)["status"] == "FAILED"


def test_google_auth_boundary_is_blocked_not_acquired() -> None:
    bundle = google_auth_blocked(
        request_id="req-3",
        evidence_id="evidence:ready-message",
        retention_expires_at="2026-08-21",
    )
    record = bundle.acquisitions[0]
    assert bundle.status == "BLOCKED_PROVIDER_INTERACTIVE_AUTH"
    assert record["status"] == "BLOCKED"
    assert record["error_class"] == "BLOCKED_PROVIDER_INTERACTIVE_AUTH"
    assert record["sha256"] == ""
