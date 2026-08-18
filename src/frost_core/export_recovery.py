from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Json = dict[str, Any]

CHATGPT_EXPORT_HOSTS = {"chatgpt.com", "www.chatgpt.com"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()[:24]}"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def safe_filename(name: str) -> str:
    leaf = Path(name).name.strip()
    if not leaf or leaf in {".", ".."}:
        raise ValueError("invalid filename")
    return leaf


def chatgpt_filename_from_signed_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in CHATGPT_EXPORT_HOSTS:
        raise ValueError("unsupported ChatGPT export URL host")
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    values = query.get("id")
    if not values:
        raise ValueError("ChatGPT export URL does not contain an id filename")
    return safe_filename(values[0])


def sanitize_error(error: BaseException) -> Json:
    return {
        "error_type": type(error).__name__,
        "message": str(error).split("https://", 1)[0].strip()[:500],
    }


@dataclass(frozen=True)
class PreservedRaw:
    filename: str
    source_path: str
    storage_path: str
    sha256: str
    size_bytes: int
    deduplicated: bool


@dataclass(frozen=True)
class ArchiveInspection:
    archive_type: str
    integrity_pass: bool
    member_count: int
    members: tuple[str, ...]
    archive_browser_html: tuple[str, ...] = ()
    error_html: tuple[str, ...] = ()
    inspection_error: str | None = None


@dataclass(frozen=True)
class PartRecord:
    ordinal: int
    filename: str
    sha256: str
    size_bytes: int
    storage_path: str


@dataclass(frozen=True)
class MultipartManifest:
    manifest_id: str
    manifest_sha256: str
    parts: tuple[PartRecord, ...]
    expected_parts: tuple[str, ...]
    missing_parts: tuple[str, ...]
    unexpected_parts: tuple[str, ...]
    provider_reports_omissions: bool
    provider_complete: bool


@dataclass(frozen=True)
class LedgerBundle:
    evidence: tuple[Json, ...] = ()
    acquisitions: tuple[Json, ...] = ()
    claim_links: tuple[Json, ...] = ()
    status: str = "UNKNOWN"
    notifications: tuple[str, ...] = ()
    diagnostics: Json = field(default_factory=dict)

    def to_json(self) -> str:
        return stable_json(asdict(self))


def preserve_raw_archive(source: Path, evidence_root: Path) -> PreservedRaw:
    source = source.resolve(strict=True)
    digest, size = sha256_file(source)
    filename = safe_filename(source.name)
    target_dir = evidence_root / "raw" / digest
    target = target_dir / filename
    target_dir.mkdir(parents=True, exist_ok=True)

    if target.exists():
        existing_sha, existing_size = sha256_file(target)
        if existing_sha != digest or existing_size != size:
            raise RuntimeError("content-addressed evidence collision")
        return PreservedRaw(filename, str(source), str(target), digest, size, True)

    fd, temp_name = tempfile.mkstemp(prefix=".incoming-", dir=target_dir)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copyfile(source, temp_path)
        copied_sha, copied_size = sha256_file(temp_path)
        if copied_sha != digest or copied_size != size:
            raise RuntimeError("raw evidence changed during copy")
        os.replace(temp_path, target)
        target.chmod(0o444)
    finally:
        temp_path.unlink(missing_ok=True)
    return PreservedRaw(filename, str(source), str(target), digest, size, False)


def inspect_archive(path: Path) -> ArchiveInspection:
    names: list[str] = []
    archive_type = "UNKNOWN"
    try:
        if zipfile.is_zipfile(path):
            archive_type = "ZIP"
            with zipfile.ZipFile(path) as archive:
                bad = archive.testzip()
                names = archive.namelist()
            integrity_pass = bad is None
            error = None if bad is None else f"zip CRC failure: {bad}"
        elif tarfile.is_tarfile(path):
            archive_type = "TAR"
            with tarfile.open(path, "r:*") as archive:
                names = [member.name for member in archive.getmembers()]
            integrity_pass = True
            error = None
        else:
            return ArchiveInspection("UNKNOWN", False, 0, (), inspection_error="unsupported archive")
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        return ArchiveInspection(archive_type, False, 0, (), inspection_error=type(exc).__name__)

    lower = [(name, name.lower()) for name in names]
    archive_browser = tuple(name for name, low in lower if low.endswith("archive_browser.html"))
    error_html = tuple(
        name
        for name, low in lower
        if low.endswith(".html") and ("error" in low or "failed" in low or "failure" in low)
    )
    return ArchiveInspection(
        archive_type=archive_type,
        integrity_pass=integrity_pass,
        member_count=len(names),
        members=tuple(names),
        archive_browser_html=archive_browser,
        error_html=error_html,
        inspection_error=error,
    )


def _manifest_payload(
    parts: Sequence[PartRecord],
    expected_parts: Sequence[str],
    missing_parts: Sequence[str],
    unexpected_parts: Sequence[str],
    provider_reports_omissions: bool,
) -> Json:
    return {
        "parts": [asdict(part) for part in parts],
        "expected_parts": list(expected_parts),
        "missing_parts": list(missing_parts),
        "unexpected_parts": list(unexpected_parts),
        "provider_reports_omissions": provider_reports_omissions,
    }


def build_multipart_manifest(
    preserved_parts: Iterable[PreservedRaw],
    *,
    expected_parts: Sequence[str] = (),
    provider_reports_omissions: bool = False,
) -> MultipartManifest:
    preserved = sorted(preserved_parts, key=lambda item: item.filename)
    part_records = tuple(
        PartRecord(index + 1, item.filename, item.sha256, item.size_bytes, item.storage_path)
        for index, item in enumerate(preserved)
    )
    actual_names = {item.filename for item in preserved}
    expected_names = tuple(dict.fromkeys(safe_filename(name) for name in expected_parts))
    missing = tuple(name for name in expected_names if name not in actual_names)
    unexpected = tuple(sorted(actual_names.difference(expected_names))) if expected_names else ()
    payload = _manifest_payload(
        part_records,
        expected_names,
        missing,
        unexpected,
        provider_reports_omissions,
    )
    manifest_sha = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    provider_complete = bool(part_records) and not missing and not provider_reports_omissions
    if not expected_names:
        provider_complete = False
    return MultipartManifest(
        manifest_id=f"manifest:{manifest_sha[:24]}",
        manifest_sha256=manifest_sha,
        parts=part_records,
        expected_parts=expected_names,
        missing_parts=missing,
        unexpected_parts=unexpected,
        provider_reports_omissions=provider_reports_omissions,
        provider_complete=provider_complete,
    )


def write_derived_manifest(manifest: MultipartManifest, evidence_root: Path) -> Path:
    payload = asdict(manifest)
    target_dir = evidence_root / "derived" / "manifests"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{manifest.manifest_sha256}.json"
    serialized = stable_json(payload) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != serialized:
            raise RuntimeError("manifest digest collision")
        return target
    target.write_text(serialized, encoding="utf-8")
    target.chmod(0o444)
    return target


def _raw_evidence_record(
    *,
    provider: str,
    source_identity: str,
    raw: PreservedRaw,
    event_time: str | None,
    provider_completeness: str,
    acquisition_time: str,
) -> Json:
    evidence_id = f"evidence:{provider.lower()}:{raw.sha256[:24]}"
    return {
        "evidence_id": evidence_id,
        "primary_evidence_type": "PROVIDER_EXPORT_EVIDENCE",
        "evidence_types_json": stable_json(["PROVIDER_EXPORT_EVIDENCE"]),
        "source_provider": provider,
        "source_identity": source_identity,
        "acquisition_time": acquisition_time,
        "source_event_time": event_time or "",
        "raw_object_identity": f"sha256:{raw.sha256}",
        "raw_filename": raw.filename,
        "raw_size_bytes": raw.size_bytes,
        "content_sha256": raw.sha256,
        "storage_uri": raw.storage_path,
        "provenance_json": stable_json({"preserved_raw": True, "deduplicated": raw.deduplicated}),
        "observation_class": "OBSERVED",
        "parent_evidence_ids_json": "[]",
        "related_claim_ids_json": "[]",
        "validation_status": "EXPORT_ACQUIRED",
        "integrity_status": "PASS",
        "provider_completeness": provider_completeness,
        "missing_data_json": "{}",
        "immutable_raw": True,
        "created_at_client": acquisition_time,
        "updated_at_client": acquisition_time,
    }


def _acquisition_record(
    *,
    provider: str,
    source_identity: str,
    retrieval_method: str,
    status: str,
    idempotency_key: str,
    created_at: str,
    evidence_id: str | None = None,
    raw: PreservedRaw | None = None,
    error_class: str = "",
    error_details: Json | None = None,
    next_action: str = "",
) -> Json:
    return {
        "attempt_id": stable_id("acq", provider, idempotency_key, status),
        "evidence_id": evidence_id or "",
        "provider": provider,
        "retrieval_method": retrieval_method,
        "source_identity": source_identity,
        "started_at": created_at,
        "finished_at": created_at,
        "status": status,
        "raw_filename": raw.filename if raw else "",
        "size_bytes": raw.size_bytes if raw else 0,
        "sha256": raw.sha256 if raw else "",
        "storage_uri": raw.storage_path if raw else "",
        "tool_identity": "frost_core.export_recovery/v1",
        "error_class": error_class,
        "error_details_json": stable_json(error_details or {}),
        "next_action": next_action,
        "idempotency_key": idempotency_key,
        "created_at_client": created_at,
    }


def ingest_takeout_parts(
    *,
    request_id: str,
    part_paths: Sequence[Path],
    evidence_root: Path,
    expected_parts: Sequence[str] = (),
    provider_reports_omissions: bool = False,
    event_time: str | None = None,
) -> LedgerBundle:
    now = utc_now()
    source_identity = f"google-takeout:{request_id}"
    preserved = tuple(preserve_raw_archive(path, evidence_root) for path in part_paths)
    inspections = {item.filename: inspect_archive(Path(item.storage_path)) for item in preserved}
    manifest = build_multipart_manifest(
        preserved,
        expected_parts=expected_parts,
        provider_reports_omissions=provider_reports_omissions,
    )
    manifest_path = write_derived_manifest(manifest, evidence_root)

    if provider_reports_omissions or manifest.missing_parts:
        export_status = "EXPORT_INCOMPLETE"
        completeness = "INCOMPLETE"
    elif manifest.provider_complete:
        export_status = "EXPORT_ACQUIRED"
        completeness = "COMPLETE"
    else:
        export_status = "EXPORT_INCOMPLETE"
        completeness = "UNKNOWN"

    evidence: list[Json] = []
    acquisitions: list[Json] = []
    parent_ids: list[str] = []
    for item in preserved:
        record = _raw_evidence_record(
            provider="Google Takeout",
            source_identity=source_identity,
            raw=item,
            event_time=event_time,
            provider_completeness=completeness,
            acquisition_time=now,
        )
        evidence.append(record)
        parent_ids.append(record["evidence_id"])
        acquisitions.append(
            _acquisition_record(
                provider="Google Takeout",
                source_identity=source_identity,
                retrieval_method="DRIVE_RAW_FILE",
                status="ACQUIRED",
                idempotency_key=f"drive-raw:{item.sha256}",
                created_at=now,
                evidence_id=record["evidence_id"],
                raw=item,
            )
        )

    manifest_evidence_id = f"evidence:google-takeout:manifest:{manifest.manifest_sha256[:24]}"
    evidence.append(
        {
            "evidence_id": manifest_evidence_id,
            "primary_evidence_type": "DERIVED_EVIDENCE",
            "evidence_types_json": stable_json(["DERIVED_EVIDENCE", "MULTIPART_MANIFEST"]),
            "source_provider": "Derived local parser",
            "source_identity": source_identity,
            "acquisition_time": now,
            "source_event_time": event_time or "",
            "raw_object_identity": manifest.manifest_id,
            "raw_filename": manifest_path.name,
            "raw_size_bytes": manifest_path.stat().st_size,
            "content_sha256": manifest.manifest_sha256,
            "storage_uri": str(manifest_path),
            "provenance_json": stable_json(
                {
                    "parent_evidence_ids": parent_ids,
                    "inspections": {name: asdict(value) for name, value in inspections.items()},
                }
            ),
            "observation_class": "DERIVED",
            "parent_evidence_ids_json": stable_json(parent_ids),
            "related_claim_ids_json": "[]",
            "validation_status": export_status,
            "integrity_status": "PASS" if all(x.integrity_pass for x in inspections.values()) else "FAIL",
            "provider_completeness": completeness,
            "missing_data_json": stable_json(
                {
                    "missing_parts": manifest.missing_parts,
                    "provider_reports_omissions": provider_reports_omissions,
                }
            ),
            "immutable_raw": False,
            "created_at_client": now,
            "updated_at_client": now,
        }
    )

    claim_id = f"claim:google-takeout:{request_id}:export-state"
    claim_link = {
        "link_id": stable_id("link", manifest_evidence_id, claim_id),
        "evidence_id": manifest_evidence_id,
        "claim_id": claim_id,
        "relation": "SUPPORTS",
        "claim_status": export_status,
        "confidence": 1.0,
        "rationale_json": stable_json(
            {
                "all_present_parts_integrity_checked": True,
                "provider_reports_omissions": provider_reports_omissions,
                "missing_parts": manifest.missing_parts,
                "physical_validation": False,
            }
        ),
        "linked_at": now,
    }
    return LedgerBundle(
        evidence=tuple(evidence),
        acquisitions=tuple(acquisitions),
        claim_links=(claim_link,),
        status=export_status,
        notifications=(export_status,),
        diagnostics={"manifest": asdict(manifest)},
    )


def google_auth_blocked(
    *,
    request_id: str,
    evidence_id: str,
    retention_expires_at: str,
) -> LedgerBundle:
    now = utc_now()
    source_identity = f"google-takeout:{request_id}"
    record = _acquisition_record(
        provider="Google Takeout",
        source_identity=source_identity,
        retrieval_method="AUTHENTICATED_BROWSER",
        status="BLOCKED",
        idempotency_key=f"{source_identity}:interactive-auth-boundary",
        created_at=now,
        evidence_id=evidence_id,
        error_class="BLOCKED_PROVIDER_INTERACTIVE_AUTH",
        error_details={"retention_expires_at": retention_expires_at},
        next_action=(
            "Use Google's authenticated Download archive flow once and place every downloaded "
            "part in the configured Drive drop zone; resume at raw-file hashing."
        ),
    )
    return LedgerBundle(acquisitions=(record,), status="BLOCKED_PROVIDER_INTERACTIVE_AUTH")


def download_chatgpt_signed_export(
    *,
    signed_url: str,
    source_identity: str,
    evidence_root: Path,
    timeout_seconds: float = 60.0,
) -> LedgerBundle:
    now = utc_now()
    filename = chatgpt_filename_from_signed_url(signed_url)
    incoming_dir = evidence_root / "incoming"
    incoming_dir.mkdir(parents=True, exist_ok=True)
    temp_path = incoming_dir / f".{stable_id('download', source_identity, filename)}.part"

    try:
        request = urllib.request.Request(
            signed_url,
            headers={"User-Agent": "centinal26-export-recovery/1"},
            method="GET",
        )
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response, temp_path.open(
            "wb"
        ) as handle:
            final_host = urllib.parse.urlsplit(response.geturl()).hostname
            if final_host not in CHATGPT_EXPORT_HOSTS:
                raise RuntimeError("unexpected signed export redirect host")
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size <= 0:
            raise RuntimeError("provider returned an empty export")
        downloaded = incoming_dir / filename
        os.replace(temp_path, downloaded)
        raw = preserve_raw_archive(downloaded, evidence_root)
        downloaded.unlink(missing_ok=True)
        if raw.sha256 != digest.hexdigest() or raw.size_bytes != size:
            raise RuntimeError("download hash mismatch after preservation")
        inspection = inspect_archive(Path(raw.storage_path))
        if not inspection.integrity_pass:
            raise RuntimeError("downloaded ChatGPT export is not a valid archive")

        evidence = _raw_evidence_record(
            provider="OpenAI ChatGPT",
            source_identity=source_identity,
            raw=raw,
            event_time=None,
            provider_completeness="UNKNOWN",
            acquisition_time=now,
        )
        acquisition = _acquisition_record(
            provider="OpenAI ChatGPT",
            source_identity=source_identity,
            retrieval_method="DIRECT_URL",
            status="ACQUIRED",
            idempotency_key=f"chatgpt:{source_identity}:{raw.sha256}",
            created_at=now,
            evidence_id=evidence["evidence_id"],
            raw=raw,
        )
        return LedgerBundle(
            evidence=(evidence,),
            acquisitions=(acquisition,),
            status="EXPORT_ACQUIRED",
            notifications=("new export bytes acquired/hash-verified",),
            diagnostics={"archive": asdict(inspection)},
        )
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        temp_path.unlink(missing_ok=True)
        acquisition = _acquisition_record(
            provider="OpenAI ChatGPT",
            source_identity=source_identity,
            retrieval_method="DIRECT_URL",
            status="FAILED",
            idempotency_key=f"chatgpt:{source_identity}:direct-url",
            created_at=now,
            error_class="PROVIDER_URL_FETCH_FAILED",
            error_details={"signed_url_present": True, **sanitize_error(exc)},
            next_action="Retry through a supported raw downloader while the provider URL is valid.",
        )
        return LedgerBundle(acquisitions=(acquisition,), status="FAILED")


def _load_json_stdin() -> Json:
    return json.load(__import__("sys").stdin)


def _path_list(values: Sequence[str]) -> list[Path]:
    return [Path(value) for value in values]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic provider export recovery controller")
    parser.add_argument(
        "mode",
        choices=("chatgpt-download", "takeout-ingest", "google-auth-blocked"),
    )
    parser.add_argument("--evidence-root", default="evidence/export-recovery")
    args = parser.parse_args(argv)
    payload = _load_json_stdin()
    evidence_root = Path(args.evidence_root)

    if args.mode == "chatgpt-download":
        bundle = download_chatgpt_signed_export(
            signed_url=str(payload["signed_url"]),
            source_identity=str(payload["source_identity"]),
            evidence_root=evidence_root,
            timeout_seconds=float(payload.get("timeout_seconds", 60.0)),
        )
    elif args.mode == "takeout-ingest":
        bundle = ingest_takeout_parts(
            request_id=str(payload["request_id"]),
            part_paths=_path_list(payload["part_paths"]),
            evidence_root=evidence_root,
            expected_parts=tuple(payload.get("expected_parts", ())),
            provider_reports_omissions=bool(payload.get("provider_reports_omissions", False)),
            event_time=payload.get("event_time"),
        )
    else:
        bundle = google_auth_blocked(
            request_id=str(payload["request_id"]),
            evidence_id=str(payload["evidence_id"]),
            retention_expires_at=str(payload["retention_expires_at"]),
        )

    print(bundle.to_json())
    return 0 if bundle.status not in {"FAILED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
