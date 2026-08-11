from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_zip_member(archive: zipfile.ZipFile, source: Path, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, source.read_bytes())


def build(site_root: Path, output_dir: Path) -> dict[str, object]:
    if not site_root.is_dir():
        raise FileNotFoundError(f"site root not found: {site_root}")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / "automation-os-site.zip"
    manifest_path = output_dir / "site-manifest.json"
    sums_path = output_dir / "SHA256SUMS"

    files = sorted(
        path
        for path in site_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    if not files:
        raise ValueError(f"site root contains no files: {site_root}")

    entries = [
        {
            "path": path.relative_to(site_root.parent).as_posix(),
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
        for path in files
    ]
    manifest = {
        "schema": "automation-os-static-site-manifest-v1",
        "source_commit": os.environ.get("GITHUB_SHA", "unknown"),
        "files": entries,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in files:
            write_zip_member(
                archive,
                path,
                path.relative_to(site_root.parent).as_posix(),
            )
        write_zip_member(archive, manifest_path, "site-manifest.json")

    sums = [
        f"{sha256_file(archive_path)}  {archive_path.name}",
        f"{sha256_file(manifest_path)}  {manifest_path.name}",
    ]
    sums_path.write_text("\n".join(sums) + "\n", encoding="utf-8")

    result = {
        "archive": archive_path.as_posix(),
        "archive_sha256": sha256_file(archive_path),
        "manifest": manifest_path.as_posix(),
        "manifest_sha256": sha256_file(manifest_path),
        "sha256sums": sums_path.as_posix(),
        "file_count": len(files),
    }
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Package the validated Automation OS static website.")
    parser.add_argument("--site-root", default="site", type=Path)
    parser.add_argument("--output-dir", default="dist", type=Path)
    args = parser.parse_args()
    build(args.site_root, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
