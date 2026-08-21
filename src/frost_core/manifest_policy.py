from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


class ManifestPolicyError(ValueError):
    """A filesystem object violates the canonical manifest policy."""


@dataclass(frozen=True)
class ManifestPolicy:
    reject_symlinks: bool = True
    reject_hardlinks: bool = True
    reject_sparse_files: bool = True
    include_permissions: bool = True
    max_files: int = 100_000
    max_total_bytes: int = 50 * 1024 * 1024 * 1024


def _safe_relative(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or not relative:
        raise ManifestPolicyError(f"unsafe relative path: {relative!r}")
    return relative


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: str | Path, *, policy: ManifestPolicy | None = None) -> dict[str, Any]:
    """Build a deterministic manifest without following filesystem indirections.

    Directory entries are sorted lexically. Symlinks, multiply-linked files, sparse
    files, sockets/devices/FIFOs, traversal, and configured resource-limit overruns
    fail closed rather than being normalized silently.
    """

    policy = policy or ManifestPolicy()
    root_path = Path(root)
    if root_path.is_symlink() and policy.reject_symlinks:
        raise ManifestPolicyError("manifest root may not be a symlink")
    if not root_path.is_dir():
        raise ManifestPolicyError("manifest root must be a directory")
    root_path = root_path.resolve()

    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for directory, dirnames, filenames in os.walk(root_path, topdown=True, followlinks=False):
        directory_path = Path(directory)
        dirnames.sort()
        filenames.sort()

        retained_dirs: list[str] = []
        for dirname in dirnames:
            child = directory_path / dirname
            mode = child.lstat().st_mode
            if stat.S_ISLNK(mode):
                if policy.reject_symlinks:
                    raise ManifestPolicyError(f"symlink directory rejected: {_safe_relative(child, root_path)}")
                continue
            if not stat.S_ISDIR(mode):
                raise ManifestPolicyError(f"non-directory traversal entry: {_safe_relative(child, root_path)}")
            retained_dirs.append(dirname)
        dirnames[:] = retained_dirs

        for filename in filenames:
            path = directory_path / filename
            info = path.lstat()
            relative = _safe_relative(path, root_path)
            if stat.S_ISLNK(info.st_mode):
                if policy.reject_symlinks:
                    raise ManifestPolicyError(f"symlink rejected: {relative}")
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ManifestPolicyError(f"non-regular file rejected: {relative}")
            if policy.reject_hardlinks and info.st_nlink > 1:
                raise ManifestPolicyError(f"hardlink rejected: {relative}")
            allocated = getattr(info, "st_blocks", 0) * 512
            if policy.reject_sparse_files and info.st_size > 0 and allocated and allocated < info.st_size:
                raise ManifestPolicyError(f"sparse file rejected: {relative}")

            total_bytes += int(info.st_size)
            if len(entries) + 1 > policy.max_files:
                raise ManifestPolicyError("manifest file-count limit exceeded")
            if total_bytes > policy.max_total_bytes:
                raise ManifestPolicyError("manifest byte limit exceeded")
            entry: dict[str, Any] = {
                "path": relative,
                "size_bytes": int(info.st_size),
                "sha256": _sha256_file(path),
            }
            if policy.include_permissions:
                entry["mode"] = format(stat.S_IMODE(info.st_mode), "04o")
            entries.append(entry)

    manifest: dict[str, Any] = {
        "schema": "frost.manifest.v1",
        "policy": {
            "symlinks": "REJECT" if policy.reject_symlinks else "SKIP",
            "hardlinks": "REJECT" if policy.reject_hardlinks else "ALLOW",
            "sparse_files": "REJECT" if policy.reject_sparse_files else "ALLOW",
            "permissions": "RECORDED" if policy.include_permissions else "OMITTED",
            "max_files": policy.max_files,
            "max_total_bytes": policy.max_total_bytes,
        },
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "entries": entries,
    }
    canonical = __import__("json").dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return manifest
