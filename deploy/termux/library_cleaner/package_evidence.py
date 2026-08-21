#!/usr/bin/env python3
"""Package Frost Forge Library Cleaner evidence into a deterministic review bundle."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import zipfile
from pathlib import Path

DEFAULT_APP_HOME = Path.home() / ".local" / "share" / "frost-library-cleaner"
DEFAULT_ARCHIVE_DIR = Path.home() / "storage" / "downloads" / "FrostForgeLibraryArchive"
DEFAULT_OUTPUT_DIR = Path.home() / "storage" / "downloads" / "FrostForgeLibraryCleanerEvidence"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def file_record(path: Path, logical_path: str) -> dict[str, object]:
    return {
        "path": logical_path,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def archive_index(archive_dir: Path) -> list[dict[str, object]]:
    return [
        file_record(path, str(path.relative_to(archive_dir)))
        for path in iter_files(archive_dir)
    ]


def collect_evidence_files(app_home: Path) -> list[tuple[Path, str]]:
    result: list[tuple[Path, str]] = []
    for name in ("config.json", "state.json", "archive-ledger.jsonl", "cleaner.log"):
        path = app_home / name
        if path.is_file():
            result.append((path, f"app/{name}"))
    for directory_name in ("ui-snapshots", "service-log"):
        directory = app_home / directory_name
        for path in iter_files(directory):
            result.append((path, f"app/{directory_name}/{path.relative_to(directory)}"))
    return sorted(result, key=lambda item: item[1])


def package_evidence(
    *,
    app_home: Path,
    archive_dir: Path,
    output_dir: Path,
    include_archived_files: bool = False,
    timestamp: str | None = None,
) -> tuple[Path, Path, dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = timestamp or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = output_dir / f"FrostForgeLibraryCleanerEvidence_{timestamp}.zip"
    checksum_path = zip_path.with_suffix(zip_path.suffix + ".sha256")

    evidence_files = collect_evidence_files(app_home)
    archives = archive_index(archive_dir)
    manifest: dict[str, object] = {
        "schema": "frost.library_cleaner.evidence.v1",
        "created_utc": timestamp,
        "app_home": str(app_home),
        "archive_dir": str(archive_dir),
        "include_archived_files": include_archived_files,
        "evidence_files": [file_record(path, logical) for path, logical in evidence_files],
        "archive_index": archives,
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path, logical in evidence_files:
            bundle.write(path, arcname=logical)
        bundle.writestr(
            "ARCHIVE_INDEX.json",
            json.dumps(archives, indent=2, sort_keys=True) + "\n",
        )
        bundle.writestr(
            "EVIDENCE_MANIFEST.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
        if include_archived_files:
            for path in iter_files(archive_dir):
                bundle.write(path, arcname=f"archived/{path.relative_to(archive_dir)}")

    bundle_digest = sha256_file(zip_path)
    checksum_path.write_text(f"{bundle_digest}  {zip_path.name}\n", encoding="utf-8")
    return zip_path, checksum_path, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-home", type=Path, default=DEFAULT_APP_HOME)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--include-archived-files", action="store_true")
    arguments = parser.parse_args()

    zip_path, checksum_path, manifest = package_evidence(
        app_home=Path(os.path.expanduser(str(arguments.app_home))),
        archive_dir=Path(os.path.expanduser(str(arguments.archive_dir))),
        output_dir=Path(os.path.expanduser(str(arguments.output_dir))),
        include_archived_files=arguments.include_archived_files,
    )
    print(
        json.dumps(
            {
                "status": "EVIDENCE_PACKAGE_CREATED",
                "zip": str(zip_path),
                "sha256_file": str(checksum_path),
                "evidence_file_count": len(manifest["evidence_files"]),
                "archive_index_count": len(manifest["archive_index"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
