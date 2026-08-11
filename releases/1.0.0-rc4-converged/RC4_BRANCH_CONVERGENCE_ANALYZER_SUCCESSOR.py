from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from rc4_successor_common import (
    GA_INSTALLER_SHA256,
    GA_PAYLOAD_SHA256,
    SCHEMA10_INSTALLER_SHA256,
    SCHEMA10_PAYLOAD_SHA256,
    TARGET_RELEASE,
    TARGET_SCHEMA,
    tree_inventory,
    verify_parent_installer,
    write_json,
)

PROVENANCE_CLASS = "RECONSTRUCTED_SUCCESSOR"


def analyze(schema10: Path, ga: Path, output: Path) -> dict[str, object]:
    if output.exists():
        shutil.rmtree(output)
    schema_tree = output / "schema10" / "tree"
    ga_tree = output / "ga" / "tree"
    reports = output / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    schema_meta = verify_parent_installer(
        schema10,
        SCHEMA10_INSTALLER_SHA256,
        SCHEMA10_PAYLOAD_SHA256,
        schema_tree,
    )
    ga_meta = verify_parent_installer(
        ga,
        GA_INSTALLER_SHA256,
        GA_PAYLOAD_SHA256,
        ga_tree,
    )

    excluded = {"MANIFEST.json"}
    schema_files = tree_inventory(schema_tree, exclude=excluded)
    ga_files = tree_inventory(ga_tree, exclude=excluded)
    schema_paths = set(schema_files)
    ga_paths = set(ga_files)

    common_same: list[dict[str, object]] = []
    changed_common: list[dict[str, object]] = []
    for rel in sorted(schema_paths & ga_paths):
        left = schema_files[rel]
        right = ga_files[rel]
        if left["sha256"] == right["sha256"]:
            common_same.append({"path": rel, **left})
        else:
            changed_common.append(
                {
                    "path": rel,
                    "schema10_sha256": left["sha256"],
                    "schema10_size_bytes": left["size_bytes"],
                    "ga_sha256": right["sha256"],
                    "ga_size_bytes": right["size_bytes"],
                }
            )

    schema_only = [
        {"path": rel, **schema_files[rel]} for rel in sorted(schema_paths - ga_paths)
    ]
    ga_only = [{"path": rel, **ga_files[rel]} for rel in sorted(ga_paths - schema_paths)]

    generated_at = datetime.now(UTC).isoformat()
    queue = {
        "format": "automation-rc4-review-queue-successor-v1",
        "provenance_class": PROVENANCE_CLASS,
        "generated_at": generated_at,
        "target_release": TARGET_RELEASE,
        "target_schema": TARGET_SCHEMA,
        "parents": {
            "schema10": {key: value for key, value in schema_meta.items() if key != "manifest"},
            "ga": {key: value for key, value in ga_meta.items() if key != "manifest"},
        },
        "common_same": common_same,
        "changed_common": changed_common,
        "schema10_only": schema_only,
        "ga_only": ga_only,
        "semantic_review_required": bool(changed_common),
        "notes": [
            "This analyzer is a reconstructed successor, not the unrecovered original companion tool.",
            "Parent installers and embedded payloads are accepted only at the exact pinned SHA-256 identities.",
            "Changed common files are never resolved by last-writer-wins; they require explicit reviewed decisions.",
        ],
    }
    write_json(reports / "RC4_REVIEW_QUEUE.json", queue)

    report = {
        "format": "automation-rc4-branch-delta-successor-v1",
        "provenance_class": PROVENANCE_CLASS,
        "generated_at": generated_at,
        "status": "PASS",
        "target_release": TARGET_RELEASE,
        "target_schema": TARGET_SCHEMA,
        "parent_verification": {
            "schema10_installer_sha256": schema_meta["installer_sha256"],
            "schema10_payload_sha256": schema_meta["payload_sha256"],
            "ga_installer_sha256": ga_meta["installer_sha256"],
            "ga_payload_sha256": ga_meta["payload_sha256"],
        },
        "counts": {
            "common_same": len(common_same),
            "changed_common": len(changed_common),
            "schema10_only": len(schema_only),
            "ga_only": len(ga_only),
        },
        "semantic_review_required": bool(changed_common),
        "review_queue": str((reports / "RC4_REVIEW_QUEUE.json").resolve()),
    }
    write_json(reports / "RC4_BRANCH_DELTA.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="RC4 branch-convergence analyzer successor")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("analyze")
    command.add_argument("--output", required=True, type=Path)
    command.add_argument("--schema10", required=True, type=Path)
    command.add_argument("--ga", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = analyze(args.schema10.expanduser(), args.ga.expanduser(), args.output.expanduser())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
