from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _run_git(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=30,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _tracked_source_inventory() -> tuple[list[dict[str, Any]], int]:
    raw = _run_git("ls-files", "-z")
    paths = sorted(item.decode("utf-8") for item in raw.split(b"\0") if item)
    entries: list[dict[str, Any]] = []
    total = 0
    for relative in paths:
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"tracked source must be a regular non-symlink file: {relative}")
        size = path.stat().st_size
        total += size
        entries.append(
            {
                "path": relative,
                "size_bytes": size,
                "sha256": _sha256_file(path),
            }
        )
    return entries, total


def build_manifest() -> dict[str, Any]:
    source_commit = _run_git("rev-parse", "HEAD").decode("ascii").strip()
    status = _run_git("status", "--porcelain", "--untracked-files=no").decode(
        "utf-8", errors="replace"
    )
    if status.strip():
        raise RuntimeError("release evidence generation requires an unmodified tracked worktree")

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    build_system = pyproject["build-system"]
    source_files, total_bytes = _tracked_source_inventory()
    required_ledgers = [
        "automation/PROJECT_STATE.json",
        "releases/RELEASE_CONTRACT.json",
        "releases/AUTHORITY_MATRIX.json",
        "releases/CURRENT_RELEASE_STATE.json",
        "releases/RELEASE_ENGINEERING_CONTRACT.json",
        "releases/COMPATIBILITY_MATRIX.json",
        "releases/DEPRECATION_REGISTRY.json",
    ]
    known_paths = {item["path"] for item in source_files}
    missing = [path for path in required_ledgers if path not in known_paths]
    if missing:
        raise RuntimeError(f"required release ledger missing from tracked source: {missing}")

    manifest: dict[str, Any] = {
        "schema": "automation.release_evidence/v1",
        "source_commit": source_commit,
        "source_tree": {
            "tracked_file_count": len(source_files),
            "tracked_total_bytes": total_bytes,
            "files": source_files,
        },
        "python_project": {
            "name": project["name"],
            "version": project["version"],
            "requires_python": project["requires-python"],
            "runtime_dependencies": sorted(project.get("dependencies", [])),
            "optional_dependencies": {
                name: sorted(values)
                for name, values in sorted(project.get("optional-dependencies", {}).items())
            },
            "entry_points": dict(sorted(project.get("scripts", {}).items())),
            "build_backend": build_system["build-backend"],
            "build_requirements": sorted(build_system.get("requires", [])),
        },
        "canonical_ledgers": {
            path: next(item["sha256"] for item in source_files if item["path"] == path)
            for path in required_ledgers
        },
        "evidence_boundaries": {
            "host_manifest_generated": True,
            "device_validation_inferred": False,
            "persistence_validation_inferred": False,
            "recovery_validation_inferred": False,
            "deployment_authorization_inferred": False,
        },
        "identity_policy": {
            "timestamp_in_identity": False,
            "same_commit_same_tracked_bytes_same_manifest": True,
        },
    }
    manifest["manifest_sha256"] = hashlib.sha256(_canonical_bytes(manifest)).hexdigest()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(manifest["manifest_sha256"])


if __name__ == "__main__":
    main()
