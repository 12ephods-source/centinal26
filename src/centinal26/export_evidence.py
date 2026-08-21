from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

SCHEMA = "centinal26-export-evidence-receipt/v1"
DEFAULT_ROOT = Path.home() / ".local" / "share" / "centinal26" / "evidence" / "exports"
_CHUNK = 1024 * 1024


class EvidenceStoreError(RuntimeError):
    """Base exception for export evidence preservation failures."""


class SourceIdentityConflict(EvidenceStoreError):
    """A provider source identity was previously bound to different bytes."""


class ObjectIntegrityError(EvidenceStoreError):
    """A content-addressed object does not match its SHA-256 identity."""


@dataclass(frozen=True)
class PreservationResult:
    status: str
    receipt_id: str
    sha256: str
    size: int
    object_path: str
    receipt_path: str


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _write_exclusive(path: Path, data: bytes, mode: int = 0o444) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            path.chmod(mode)
        except OSError:
            pass
        _fsync_dir(path.parent)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return True


@contextmanager
def _store_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".ingest.lock"
    with lock_path.open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _load_receipts(root: Path) -> Iterator[dict[str, Any]]:
    receipts_dir = root / "receipts"
    if not receipts_dir.exists():
        return
    for path in sorted(receipts_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvidenceStoreError(f"INVALID_RECEIPT:{path.name}") from exc
        if payload.get("schema") != SCHEMA:
            raise EvidenceStoreError(f"UNSUPPORTED_RECEIPT_SCHEMA:{path.name}")
        yield payload


def _strong_identity_conflict(
    existing: dict[str, Any],
    *,
    provider: str,
    message_id: str | None,
    export_id: str | None,
    sha256: str,
) -> bool:
    if existing.get("provider") != provider:
        return False
    identity = existing.get("source_identity") or {}
    same_message = message_id is not None and identity.get("message_id") == message_id
    same_export = export_id is not None and identity.get("export_id") == export_id
    if not (same_message or same_export):
        return False
    return (existing.get("content") or {}).get("sha256") != sha256


def _receipt_id(
    *,
    provider: str,
    message_id: str | None,
    export_id: str | None,
    sha256: str,
    original_filename: str,
    message_date: str | None,
) -> str:
    identity = {
        "provider": provider,
        "message_id": message_id,
        "export_id": export_id,
        "sha256": sha256,
    }
    if message_id is None and export_id is None:
        identity["original_filename"] = original_filename
        identity["message_date"] = message_date
    return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def _verify_existing_object(path: Path, expected_sha256: str, expected_size: int) -> None:
    actual_sha256, actual_size = _hash_file(path)
    if actual_sha256 != expected_sha256 or actual_size != expected_size:
        raise ObjectIntegrityError(f"OBJECT_INTEGRITY_FAILURE:{expected_sha256}")


def _preserve_object(
    source: Path, target: Path, expected_sha256: str, expected_size: int
) -> bool:
    if target.exists():
        _verify_existing_object(target, expected_sha256, expected_size)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    except FileExistsError:
        _verify_existing_object(target, expected_sha256, expected_size)
        return False
    digest = hashlib.sha256()
    copied = 0
    try:
        with source.open("rb") as src, os.fdopen(fd, "wb") as dst:
            while chunk := src.read(_CHUNK):
                digest.update(chunk)
                copied += len(chunk)
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        if digest.hexdigest() != expected_sha256 or copied != expected_size:
            raise EvidenceStoreError("SOURCE_CHANGED_DURING_INGEST")
        try:
            target.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        except OSError:
            pass
        _fsync_dir(target.parent)
        return True
    except (OSError, EvidenceStoreError):
        target.unlink(missing_ok=True)
        raise


def preserve_export(
    source_file: str | Path,
    *,
    provider: str,
    root: str | Path = DEFAULT_ROOT,
    message_id: str | None = None,
    export_id: str | None = None,
    message_date: str | None = None,
    subject: str | None = None,
    retrieved_at: str | None = None,
) -> PreservationResult:
    source = Path(source_file).expanduser().resolve()
    store_root = Path(root).expanduser().resolve()
    provider = provider.strip()
    if not provider:
        raise ValueError("provider is required")
    if not source.is_file():
        raise FileNotFoundError(source)
    message_id = _normalize_optional(message_id)
    export_id = _normalize_optional(export_id)
    message_date = _normalize_optional(message_date)
    subject = _normalize_optional(subject)
    retrieved_at = _normalize_optional(retrieved_at) or _utc_now()
    sha256, size = _hash_file(source)
    object_relpath = Path("objects") / "sha256" / sha256[:2] / sha256
    object_path = store_root / object_relpath
    rid = _receipt_id(
        provider=provider,
        message_id=message_id,
        export_id=export_id,
        sha256=sha256,
        original_filename=source.name,
        message_date=message_date,
    )
    receipt_path = store_root / "receipts" / f"{rid}.json"
    with _store_lock(store_root):
        for existing in _load_receipts(store_root):
            if _strong_identity_conflict(
                existing,
                provider=provider,
                message_id=message_id,
                export_id=export_id,
                sha256=sha256,
            ):
                raise SourceIdentityConflict("SOURCE_IDENTITY_CONFLICT")
        if receipt_path.exists():
            existing = json.loads(receipt_path.read_text(encoding="utf-8"))
            existing_sha = (existing.get("content") or {}).get("sha256")
            if existing_sha != sha256:
                raise EvidenceStoreError("RECEIPT_ID_COLLISION")
            _verify_existing_object(object_path, sha256, size)
            return PreservationResult(
                status="DUPLICATE_SOURCE",
                receipt_id=rid,
                sha256=sha256,
                size=size,
                object_path=str(object_path),
                receipt_path=str(receipt_path),
            )
        object_created = _preserve_object(source, object_path, sha256, size)
        receipt = {
            "schema": SCHEMA,
            "receipt_id": rid,
            "provider": provider,
            "source_identity": {"message_id": message_id, "export_id": export_id},
            "source_metadata": {
                "original_filename": source.name,
                "message_date": message_date,
                "subject": subject,
                "retrieved_at": retrieved_at,
                "ingested_at": _utc_now(),
            },
            "content": {
                "sha256": sha256,
                "size": size,
                "object_relpath": object_relpath.as_posix(),
                "raw_preserved_unextracted": True,
            },
        }
        receipt_bytes = (_canonical_json(receipt) + "\n").encode("utf-8")
        if not _write_exclusive(receipt_path, receipt_bytes):
            raise EvidenceStoreError("RECEIPT_RACE")
        index_path = store_root / "index" / "receipts.jsonl"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("ab") as handle:
            handle.write(receipt_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_dir(index_path.parent)
        return PreservationResult(
            status="PRESERVED" if object_created else "REUSED_OBJECT",
            receipt_id=rid,
            sha256=sha256,
            size=size,
            object_path=str(object_path),
            receipt_path=str(receipt_path),
        )


def verify_receipt(root: str | Path, receipt_id: str) -> PreservationResult:
    store_root = Path(root).expanduser().resolve()
    receipt_path = store_root / "receipts" / f"{receipt_id}.json"
    if not receipt_path.is_file():
        raise FileNotFoundError(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != SCHEMA or receipt.get("receipt_id") != receipt_id:
        raise EvidenceStoreError("INVALID_RECEIPT")
    content = receipt.get("content") or {}
    sha256 = content.get("sha256")
    size = content.get("size")
    relpath = content.get("object_relpath")
    if not isinstance(sha256, str) or len(sha256) != 64:
        raise EvidenceStoreError("INVALID_RECEIPT_SHA256")
    if not isinstance(size, int) or size < 0 or not isinstance(relpath, str):
        raise EvidenceStoreError("INVALID_RECEIPT_CONTENT")
    object_path = (store_root / relpath).resolve()
    object_root = (store_root / "objects").resolve()
    try:
        object_path.relative_to(object_root)
    except ValueError as exc:
        raise EvidenceStoreError("INVALID_OBJECT_PATH") from exc
    _verify_existing_object(object_path, sha256, size)
    return PreservationResult(
        status="VERIFIED",
        receipt_id=receipt_id,
        sha256=sha256,
        size=size,
        object_path=str(object_path),
        receipt_path=str(receipt_path),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preserve provider export bytes in the neutral evidence store."
    )
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Evidence store root")
    sub = parser.add_subparsers(dest="command", required=True)
    preserve = sub.add_parser("preserve", help="Preserve one raw provider export without extraction")
    preserve.add_argument("source_file")
    preserve.add_argument("--provider", required=True)
    preserve.add_argument("--message-id")
    preserve.add_argument("--export-id")
    preserve.add_argument("--message-date")
    preserve.add_argument("--subject")
    preserve.add_argument("--retrieved-at")
    verify = sub.add_parser("verify", help="Verify an immutable receipt and its raw object")
    verify.add_argument("receipt_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "preserve":
            result = preserve_export(
                args.source_file,
                provider=args.provider,
                root=args.root,
                message_id=args.message_id,
                export_id=args.export_id,
                message_date=args.message_date,
                subject=args.subject,
                retrieved_at=args.retrieved_at,
            )
        else:
            result = verify_receipt(args.root, args.receipt_id)
    except (EvidenceStoreError, FileNotFoundError, ValueError) as exc:
        print(_canonical_json({"status": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 2
    print(_canonical_json(asdict(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
