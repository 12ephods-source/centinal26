from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rc4_successor_common import (
    TARGET_RELEASE,
    TARGET_SCHEMA,
    sha256_file,
    tree_digest,
    tree_inventory,
    write_json,
)

PROVENANCE_CLASS = "RECONSTRUCTED_SUCCESSOR"


def _safe_relative(value: str) -> Path:
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe relative path: {value}")
    return rel


def _copy(source: Path, destination_root: Path, rel_text: str) -> None:
    rel = _safe_relative(rel_text)
    if not source.is_file():
        raise ValueError(f"source file missing: {source}")
    destination = destination_root / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _validate_decisions(queue: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    if decisions.get("format") != "automation-rc4-merge-decisions-v1":
        raise ValueError("unexpected merge-decisions format")
    if decisions.get("target_release") != TARGET_RELEASE:
        raise ValueError("merge-decisions target release mismatch")
    if int(decisions.get("target_schema", -1)) != TARGET_SCHEMA:
        raise ValueError("merge-decisions target schema mismatch")

    changed = {item["path"] for item in queue.get("changed_common", [])}
    provided = set((decisions.get("changed_common") or {}).keys())
    if changed != provided:
        raise ValueError("changed_common decisions do not exactly match the review queue")

    if changed:
        reviewer = str(decisions.get("reviewed_by", ""))
        reviewed_at = str(decisions.get("reviewed_at", ""))
        if not reviewer or reviewer.startswith("REQUIRED_"):
            raise ValueError("changed common files require a real reviewed_by value")
        if not reviewed_at or reviewed_at.startswith("REQUIRED_"):
            raise ValueError("changed common files require a real reviewed_at value")

    for rel in sorted(changed):
        decision = decisions["changed_common"][rel]
        resolution = decision.get("resolution")
        if resolution not in {"schema10", "ga", "custom"}:
            raise ValueError(f"invalid resolution for {rel}: {resolution}")
        if not str(decision.get("rationale", "")).strip():
            raise ValueError(f"missing semantic rationale for {rel}")
        tests = decision.get("tests")
        if not isinstance(tests, list) or not tests or not all(str(item).strip() for item in tests):
            raise ValueError(f"missing regression-test declarations for {rel}")
        if resolution == "custom":
            source = decision.get("custom_source_path")
            expected = decision.get("custom_sha256")
            if not source or not expected:
                raise ValueError(f"custom resolution for {rel} requires source path and SHA-256")
            path = Path(source).expanduser()
            if not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"custom source identity verification failed for {rel}")
    return decisions


def build(analysis: Path, decisions_path: Path, output: Path) -> dict[str, Any]:
    queue_path = analysis / "reports" / "RC4_REVIEW_QUEUE.json"
    if not queue_path.is_file():
        raise ValueError("RC4_REVIEW_QUEUE.json missing")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    if queue.get("format") != "automation-rc4-review-queue-successor-v1":
        raise ValueError("review queue was not produced by the successor analyzer")
    decisions = _validate_decisions(
        queue,
        json.loads(decisions_path.read_text(encoding="utf-8")),
    )

    schema_root = analysis / "schema10" / "tree"
    ga_root = analysis / "ga" / "tree"
    if output.exists():
        shutil.rmtree(output)
    tree = output / "tree"
    reports = output / "reports"
    tree.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    provenance: list[dict[str, Any]] = []

    def take(rel: str, source_root: Path, source_label: str, decision: dict[str, Any] | None = None) -> None:
        _copy(source_root / _safe_relative(rel), tree, rel)
        destination = tree / _safe_relative(rel)
        record: dict[str, Any] = {
            "path": rel,
            "source": source_label,
            "sha256": sha256_file(destination),
        }
        if decision is not None:
            record["rationale"] = decision["rationale"]
            record["declared_tests"] = decision["tests"]
        provenance.append(record)

    for item in queue.get("common_same", []):
        take(item["path"], schema_root, "schema10+ga-identical")
    for item in queue.get("schema10_only", []):
        take(item["path"], schema_root, "schema10-only")
    for item in queue.get("ga_only", []):
        take(item["path"], ga_root, "ga-only")

    changed_map = decisions.get("changed_common") or {}
    for item in queue.get("changed_common", []):
        rel = item["path"]
        decision = changed_map[rel]
        resolution = decision["resolution"]
        if resolution == "schema10":
            take(rel, schema_root, "reviewed-schema10", decision)
        elif resolution == "ga":
            take(rel, ga_root, "reviewed-ga", decision)
        else:
            custom = Path(decision["custom_source_path"]).expanduser()
            _copy(custom, tree, rel)
            provenance.append(
                {
                    "path": rel,
                    "source": "reviewed-custom",
                    "sha256": sha256_file(tree / _safe_relative(rel)),
                    "custom_source_sha256": decision["custom_sha256"],
                    "rationale": decision["rationale"],
                    "declared_tests": decision["tests"],
                }
            )

    inventory = tree_inventory(tree)
    digest = tree_digest(tree)
    manifest = {
        "format": "automation-rc4-successor-candidate-manifest-v1",
        "provenance_class": PROVENANCE_CLASS,
        "generated_at": datetime.now(UTC).isoformat(),
        "release": TARGET_RELEASE,
        "schema_version": TARGET_SCHEMA,
        "candidate_tree_root_sha256": digest,
        "installable": False,
        "promotion_performed": False,
        "files": [
            {"path": rel, "sha256": meta["sha256"], "size_bytes": meta["size_bytes"]}
            for rel, meta in sorted(inventory.items())
        ],
        "file_provenance": sorted(provenance, key=lambda item: item["path"]),
        "review": {
            "reviewed_by": decisions.get("reviewed_by"),
            "reviewed_at": decisions.get("reviewed_at"),
            "decisions_sha256": sha256_file(decisions_path),
            "review_queue_sha256": sha256_file(queue_path),
        },
        "notes": [
            "This candidate was constructed by a reconstructed successor, not the unrecovered original constructor.",
            "Construction does not imply host qualification, physical validation, certification, installability, or promotion.",
        ],
    }
    write_json(tree / "MANIFEST.json", manifest)

    report = {
        "format": "automation-rc4-construction-manifest-successor-v1",
        "provenance_class": PROVENANCE_CLASS,
        "status": "PASS",
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_tree": str(tree.resolve()),
        "candidate_tree_root_sha256": digest,
        "candidate_manifest_sha256": sha256_file(tree / "MANIFEST.json"),
        "decisions_sha256": sha256_file(decisions_path),
        "files": len(inventory),
        "installable": False,
        "promotion_performed": False,
    }
    write_json(reports / "RC4_CONSTRUCTION_MANIFEST.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="RC4 candidate-constructor successor")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("build")
    command.add_argument("--analysis", required=True, type=Path)
    command.add_argument("--decisions", required=True, type=Path)
    command.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = build(args.analysis, args.decisions, args.output)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
