from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence

from centinal26.wordbook import WordbookStore

ARCHIVE_SCHEMA = "centinal26-wordbook-archive-v1"
DEFAULT_MAX_CONVERSATIONS_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_MEMBERS = 10000
DEFAULT_MAX_COMPRESSION_RATIO = 1000.0
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class ArchiveImportReport:
    schema: str
    archive_name: str
    archive_sha256: str
    conversations_member: str
    conversations_sha256: str
    conversations_bytes: int
    archive_members: int
    user_messages: int
    non_user_messages: int
    duplicate_messages: int
    tokens: int
    ledger_recorded: bool
    corpus_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_member_name(name: str) -> bool:
    if not name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == stat.S_IFLNK


def _select_conversations_member(
    archive: zipfile.ZipFile,
    *,
    max_members: int,
    max_conversations_bytes: int,
    max_compression_ratio: float,
) -> zipfile.ZipInfo:
    members = archive.infolist()
    if len(members) > max_members:
        raise ValueError(f"archive contains too many members: {len(members)} > {max_members}")

    candidates = [
        info
        for info in members
        if not info.is_dir() and PurePosixPath(info.filename).name == "conversations.json"
    ]
    if len(candidates) != 1:
        raise ValueError(
            "ChatGPT export ZIP must contain exactly one unambiguous conversations.json"
        )

    info = candidates[0]
    if not _safe_member_name(info.filename):
        raise ValueError("unsafe conversations.json member path")
    if _is_symlink(info):
        raise ValueError("conversations.json may not be a symbolic link")
    if info.flag_bits & 0x1:
        raise ValueError("encrypted ChatGPT export members are not supported")
    if info.file_size > max_conversations_bytes:
        raise ValueError(
            f"conversations.json exceeds configured limit: {info.file_size} bytes"
        )
    if info.file_size and info.compress_size == 0:
        raise ValueError("invalid compressed size for conversations.json")
    if info.file_size:
        ratio = info.file_size / max(1, info.compress_size)
        if ratio > max_compression_ratio:
            raise ValueError(
                f"conversations.json compression ratio exceeds limit: {ratio:.1f}"
            )
    return info


def _copy_member_to_temp(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    max_bytes: int,
) -> tuple[Path, str, int]:
    digest = hashlib.sha256()
    total = 0
    handle = tempfile.NamedTemporaryFile(prefix="wordbook-", suffix=".json", delete=False)
    temp_path = Path(handle.name)
    try:
        with handle, archive.open(info, "r") as source:
            while True:
                chunk = source.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("conversations.json exceeded configured limit while reading")
                digest.update(chunk)
                handle.write(chunk)
        if total != info.file_size:
            raise ValueError(
                f"conversations.json size mismatch: metadata={info.file_size}, read={total}"
            )
        return temp_path, digest.hexdigest(), total
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _record_archive_import(
    store: WordbookStore,
    *,
    archive_name: str,
    archive_sha256: str,
    member_name: str,
    member_sha256: str,
    member_size: int,
    stats: dict[str, int],
) -> bool:
    store.conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wordbook_archive_imports (
            id INTEGER PRIMARY KEY,
            archive_name TEXT NOT NULL,
            archive_sha256 TEXT NOT NULL,
            member_name TEXT NOT NULL,
            member_sha256 TEXT NOT NULL,
            member_size INTEGER NOT NULL,
            stats_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(archive_sha256, member_sha256)
        )
        """
    )
    store.conn.execute(
        """
        INSERT OR IGNORE INTO wordbook_archive_imports
            (archive_name, archive_sha256, member_name, member_sha256, member_size, stats_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            archive_name,
            archive_sha256,
            member_name,
            member_sha256,
            member_size,
            json.dumps(stats, sort_keys=True),
        ),
    )
    inserted = bool(store.conn.execute("SELECT changes()").fetchone()[0])
    store.conn.commit()
    return inserted


def ingest_chatgpt_zip(
    store: WordbookStore,
    path: str | Path,
    *,
    max_conversations_bytes: int = DEFAULT_MAX_CONVERSATIONS_BYTES,
    max_members: int = DEFAULT_MAX_MEMBERS,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
) -> ArchiveImportReport:
    archive_path = Path(path)
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    if max_conversations_bytes < 1 or max_members < 1 or max_compression_ratio <= 0:
        raise ValueError("archive limits must be positive")
    if not zipfile.is_zipfile(archive_path):
        raise ValueError("input is not a valid ZIP archive")

    archive_sha = sha256_file(archive_path)
    with zipfile.ZipFile(archive_path, "r") as archive:
        info = _select_conversations_member(
            archive,
            max_members=max_members,
            max_conversations_bytes=max_conversations_bytes,
            max_compression_ratio=max_compression_ratio,
        )
        temp_path, member_sha, member_size = _copy_member_to_temp(
            archive,
            info,
            max_bytes=max_conversations_bytes,
        )

    try:
        stats = store.ingest_chatgpt_export(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    recorded = _record_archive_import(
        store,
        archive_name=archive_path.name,
        archive_sha256=archive_sha,
        member_name=info.filename,
        member_sha256=member_sha,
        member_size=member_size,
        stats=stats,
    )
    return ArchiveImportReport(
        schema=ARCHIVE_SCHEMA,
        archive_name=archive_path.name,
        archive_sha256=archive_sha,
        conversations_member=info.filename,
        conversations_sha256=member_sha,
        conversations_bytes=member_size,
        archive_members=len(zipfile.ZipFile(archive_path, "r").infolist()),
        user_messages=int(stats.get("user_messages", 0)),
        non_user_messages=int(stats.get("non_user_messages", 0)),
        duplicate_messages=int(stats.get("duplicate_messages", 0)),
        tokens=int(stats.get("tokens", 0)),
        ledger_recorded=recorded,
        corpus_sha256=store.corpus_digest(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="centinal26-wordbook-archive")
    parser.add_argument("archive", help="ChatGPT data-export ZIP")
    parser.add_argument("--db", default="wordbook.sqlite3", help="Wordbook SQLite database")
    parser.add_argument("--report", help="optional JSON import report path")
    parser.add_argument(
        "--max-conversations-mib",
        type=int,
        default=DEFAULT_MAX_CONVERSATIONS_BYTES // (1024 * 1024),
    )
    parser.add_argument("--max-members", type=int, default=DEFAULT_MAX_MEMBERS)
    parser.add_argument(
        "--max-compression-ratio",
        type=float,
        default=DEFAULT_MAX_COMPRESSION_RATIO,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    max_bytes = args.max_conversations_mib * 1024 * 1024
    with WordbookStore(args.db) as store:
        report = ingest_chatgpt_zip(
            store,
            args.archive,
            max_conversations_bytes=max_bytes,
            max_members=args.max_members,
            max_compression_ratio=args.max_compression_ratio,
        )
    rendered = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered, encoding="utf-8")
        os.chmod(report_path, 0o600)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
