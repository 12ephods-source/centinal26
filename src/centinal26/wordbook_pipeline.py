from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from centinal26.export_evidence import DEFAULT_ROOT as DEFAULT_EVIDENCE_ROOT
from centinal26.export_evidence import PreservationResult, preserve_export, verify_receipt
from centinal26.wordbook import Attribution, WordbookStore
from centinal26.wordbook_archive import ArchiveImportReport, ingest_chatgpt_zip

PIPELINE_SCHEMA = "centinal26-wordbook-pipeline-v1"
DICTIONARY_SCHEMA = "centinal26-wordbook-dictionary-v1"
DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "centinal26" / "wordbook"
DEFAULT_DB = DEFAULT_STATE_DIR / "wordbook.sqlite3"
DEFAULT_PIPELINE_REPORT = DEFAULT_STATE_DIR / "LAST_CORPUS_BUILD.json"
DEFAULT_DICTIONARY = DEFAULT_STATE_DIR / "WORD_BOOK_DICTIONARY.json"
DEFAULT_EVOLUTION = DEFAULT_STATE_DIR / "WORD_BOOK_EVOLUTION.json"
DEFAULT_DOWNLOAD_DIRS = (
    Path.home() / "storage" / "downloads",
    Path.home() / "storage" / "shared" / "Download",
)


@dataclass(frozen=True)
class PipelineReport:
    schema: str
    created_at: str
    source_mode: str
    preservation_status: str
    receipt_id: str
    raw_sha256: str
    raw_size: int
    object_path: str
    archive_import: dict[str, object]
    corpus_sha256: str
    dictionary_sha256: str
    dictionary_path: str
    evolution_sha256: str
    evolution_path: str
    promoted_generations: int
    rejected_generations: int
    database_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_private_json(path: Path, payload: object) -> str:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temp.write_text(rendered, encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)
    os.chmod(path, 0o600)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _is_chatgpt_export_zip(path: Path) -> bool:
    if not path.is_file() or path.suffix.casefold() != ".zip":
        return False
    try:
        if not zipfile.is_zipfile(path):
            return False
        with zipfile.ZipFile(path, "r") as archive:
            candidates = [
                info
                for info in archive.infolist()
                if not info.is_dir()
                and PurePosixPath(info.filename).name == "conversations.json"
            ]
        return len(candidates) == 1
    except (OSError, zipfile.BadZipFile):
        return False


def discover_latest_export(download_dirs: tuple[Path, ...] | list[Path]) -> Path:
    candidates: list[Path] = []
    for directory in download_dirs:
        directory = directory.expanduser()
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if _is_chatgpt_export_zip(path):
                candidates.append(path)
    if not candidates:
        raise FileNotFoundError("NO_CHATGPT_EXPORT_ZIP_FOUND")
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def _dictionary_payload(store: WordbookStore) -> dict[str, object]:
    word_rows = store.conn.execute(
        """
        SELECT token, COUNT(*) AS count
        FROM observations
        WHERE attribution = ?
        GROUP BY token
        ORDER BY count DESC, token ASC
        """,
        (Attribution.USER_DIRECT.value,),
    ).fetchall()
    phrase_rows = store.conn.execute(
        """
        SELECT phrase, n, COUNT(*) AS count
        FROM phrases
        WHERE attribution = ?
        GROUP BY phrase, n
        ORDER BY count DESC, n DESC, phrase ASC
        """,
        (Attribution.USER_DIRECT.value,),
    ).fetchall()
    rejected_rows = store.conn.execute(
        """
        SELECT normalized_text, reason, created_at
        FROM rejections
        ORDER BY normalized_text
        """
    ).fetchall()
    meta_rows = store.conn.execute(
        """
        SELECT token, COUNT(*) AS count
        FROM observations
        WHERE attribution = ?
        GROUP BY token
        ORDER BY count DESC, token ASC
        """,
        (Attribution.META_REFERENCE.value,),
    ).fetchall()
    return {
        "schema": DICTIONARY_SCHEMA,
        "corpus_sha256": store.corpus_digest(),
        "ordinary_words": [
            {"word": str(row["token"]), "count": int(row["count"])} for row in word_rows
        ],
        "ordinary_phrases": [
            {
                "phrase": str(row["phrase"]),
                "n": int(row["n"]),
                "count": int(row["count"]),
            }
            for row in phrase_rows
        ],
        "meta_reference_words": [
            {"word": str(row["token"]), "count": int(row["count"])} for row in meta_rows
        ],
        "rejections": [
            {
                "text": str(row["normalized_text"]),
                "reason": row["reason"],
                "created_at": row["created_at"],
            }
            for row in rejected_rows
        ],
    }


def _verified_preservation(
    *,
    evidence_root: Path,
    source_file: Path | None,
    receipt_id: str | None,
    provider: str,
    message_id: str | None,
    export_id: str | None,
    message_date: str | None,
    subject: str | None,
) -> tuple[str, PreservationResult]:
    if (source_file is None) == (receipt_id is None):
        raise ValueError("provide exactly one of source_file or receipt_id")
    if source_file is not None:
        preserved = preserve_export(
            source_file,
            provider=provider,
            root=evidence_root,
            message_id=message_id,
            export_id=export_id,
            message_date=message_date,
            subject=subject,
        )
        verified = verify_receipt(evidence_root, preserved.receipt_id)
        if verified.sha256 != preserved.sha256 or verified.object_path != preserved.object_path:
            raise RuntimeError("PRESERVE_VERIFY_MISMATCH")
        return preserved.status, verified
    verified = verify_receipt(evidence_root, str(receipt_id))
    return "VERIFIED_EXISTING_RECEIPT", verified


def run_pipeline(
    *,
    source_file: str | Path | None = None,
    receipt_id: str | None = None,
    provider: str = "openai",
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
    database: str | Path = DEFAULT_DB,
    state_dir: str | Path = DEFAULT_STATE_DIR,
    message_id: str | None = None,
    export_id: str | None = None,
    message_date: str | None = None,
    subject: str | None = None,
) -> PipelineReport:
    evidence_root_path = Path(evidence_root).expanduser().resolve()
    database_path = Path(database).expanduser().resolve()
    state_path = Path(state_dir).expanduser().resolve()
    source_path = None if source_file is None else Path(source_file).expanduser().resolve()

    preservation_status, verified = _verified_preservation(
        evidence_root=evidence_root_path,
        source_file=source_path,
        receipt_id=receipt_id,
        provider=provider,
        message_id=message_id,
        export_id=export_id,
        message_date=message_date,
        subject=subject,
    )

    state_path.mkdir(parents=True, exist_ok=True)
    os.chmod(state_path, 0o700)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with WordbookStore(database_path) as store:
        archive_report: ArchiveImportReport = ingest_chatgpt_zip(store, verified.object_path)
        dictionary = _dictionary_payload(store)
        dictionary_path = state_path / DEFAULT_DICTIONARY.name
        dictionary_sha = _write_private_json(dictionary_path, dictionary)

        evolution = store.evolve()
        evolution_payload = evolution.to_dict()
        evolution_path = state_path / DEFAULT_EVOLUTION.name
        evolution_sha = _write_private_json(evolution_path, evolution_payload)
        corpus_sha = store.corpus_digest()

    return PipelineReport(
        schema=PIPELINE_SCHEMA,
        created_at=_utc_now(),
        source_mode="source_file" if source_path is not None else "receipt",
        preservation_status=preservation_status,
        receipt_id=verified.receipt_id,
        raw_sha256=verified.sha256,
        raw_size=verified.size,
        object_path=verified.object_path,
        archive_import=archive_report.to_dict(),
        corpus_sha256=corpus_sha,
        dictionary_sha256=dictionary_sha,
        dictionary_path=str(dictionary_path),
        evolution_sha256=evolution_sha,
        evolution_path=str(evolution_path),
        promoted_generations=evolution.promoted_generations,
        rejected_generations=evolution.rejected_generations,
        database_path=str(database_path),
    )


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--report", default=str(DEFAULT_PIPELINE_REPORT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="centinal26-wordbook-pipeline",
        description=(
            "Preserve a ChatGPT export as canonical evidence, verify it, derive the Wordbook "
            "index, run the 100-generation campaign, and emit hashed artifacts."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    source = sub.add_parser("source", help="preserve and process one downloaded export ZIP")
    source.add_argument("source_file")
    source.add_argument("--message-id")
    source.add_argument("--export-id")
    source.add_argument("--message-date")
    source.add_argument("--subject")
    _add_common(source)

    receipt = sub.add_parser("receipt", help="process one already-preserved export receipt")
    receipt.add_argument("receipt_id")
    _add_common(receipt)

    latest = sub.add_parser(
        "latest",
        help="discover the newest local ChatGPT export ZIP, preserve it, and process it",
    )
    latest.add_argument(
        "--download-dir",
        action="append",
        default=[],
        help="download directory; repeat to add multiple locations",
    )
    latest.add_argument("--message-id")
    latest.add_argument("--export-id")
    latest.add_argument("--message-date")
    latest.add_argument("--subject")
    _add_common(latest)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "receipt":
            result = run_pipeline(
                receipt_id=args.receipt_id,
                provider=args.provider,
                evidence_root=args.evidence_root,
                database=args.db,
                state_dir=args.state_dir,
            )
        else:
            if args.command == "latest":
                dirs = (
                    [Path(value) for value in args.download_dir]
                    if args.download_dir
                    else list(DEFAULT_DOWNLOAD_DIRS)
                )
                source_file = discover_latest_export(dirs)
            else:
                source_file = Path(args.source_file)
            result = run_pipeline(
                source_file=source_file,
                provider=args.provider,
                evidence_root=args.evidence_root,
                database=args.db,
                state_dir=args.state_dir,
                message_id=args.message_id,
                export_id=args.export_id,
                message_date=args.message_date,
                subject=args.subject,
            )
        report_path = Path(args.report).expanduser().resolve()
        payload = result.to_dict()
        report_sha = _write_private_json(report_path, payload)
        output = {**payload, "report_path": str(report_path), "report_sha256": report_sha}
    except (FileNotFoundError, OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
