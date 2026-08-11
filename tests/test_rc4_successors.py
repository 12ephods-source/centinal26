from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

RELEASE_DIR = Path(__file__).resolve().parents[1] / "releases" / "1.0.0-rc4-converged"


def load_module(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RELEASE_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = load_module("rc4_successor_common", "rc4_successor_common.py")
constructor = load_module(
    "rc4_constructor_successor",
    "RC4_CANDIDATE_CONSTRUCTOR_SUCCESSOR.py",
)
host = load_module(
    "rc4_host_successor",
    "RC4_HOST_QUALIFICATION_HARNESS_SUCCESSOR.py",
)
evidence = load_module(
    "rc4_evidence_successor",
    "RC4_PROMOTION_EVIDENCE_GATE_SUCCESSOR.py",
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_candidate(tmp_path: Path) -> Path:
    analysis = tmp_path / "analysis"
    schema = analysis / "schema10" / "tree"
    ga = analysis / "ga" / "tree"
    write(schema / "changed.txt", "schema10\n")
    write(ga / "changed.txt", "ga\n")
    write(schema / "same.txt", "same\n")
    write(ga / "same.txt", "same\n")
    write(schema / "only-schema.txt", "schema\n")
    write(ga / "only-ga.txt", "ga-only\n")
    write(schema / "valid.py", "VALUE = 1\n")
    write(schema / "valid.sh", "#!/usr/bin/env bash\necho ok\n")
    write(schema / "config.json", '{"ok": true}\n')

    queue = {
        "format": "automation-rc4-review-queue-successor-v1",
        "changed_common": [{"path": "changed.txt"}],
        "common_same": [{"path": "same.txt"}],
        "schema10_only": [
            {"path": "only-schema.txt"},
            {"path": "valid.py"},
            {"path": "valid.sh"},
            {"path": "config.json"},
        ],
        "ga_only": [{"path": "only-ga.txt"}],
    }
    reports = analysis / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "RC4_REVIEW_QUEUE.json").write_text(json.dumps(queue), encoding="utf-8")

    decisions = {
        "format": "automation-rc4-merge-decisions-v1",
        "target_release": "1.0.0-rc4-converged",
        "target_schema": 10,
        "reviewed_by": "Test Reviewer",
        "reviewed_at": "2026-08-11T12:00:00Z",
        "changed_common": {
            "changed.txt": {
                "resolution": "schema10",
                "rationale": "Synthetic regression fixture chooses the schema-10 branch.",
                "tests": ["test_rc4_successors"],
            }
        },
    }
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
    output = tmp_path / "candidate"
    report = constructor.build(analysis, decisions_path, output)
    assert report["status"] == "PASS"
    return output / "tree"


def test_payload_heredoc_extraction(tmp_path: Path) -> None:
    installer = tmp_path / "installer.sh"
    installer.write_text(
        "cat > payload.b64 <<'PAYLOAD_B64'\nYWJj\nPAYLOAD_B64\necho done\n",
        encoding="utf-8",
    )
    assert common.extract_payload_b64(installer) == b"abc"


def test_constructor_requires_exact_review_queue(tmp_path: Path) -> None:
    tree = make_candidate(tmp_path)
    assert (tree / "changed.txt").read_text(encoding="utf-8") == "schema10\n"
    manifest = common.candidate_manifest(tree)
    assert manifest["release"] == "1.0.0-rc4-converged"
    assert manifest["schema_version"] == 10
    assert manifest["installable"] is False


def test_host_qualification_is_non_mutating(tmp_path: Path) -> None:
    tree = make_candidate(tmp_path)
    before = common.candidate_digest(tree)
    report = host.qualify(tree, tmp_path / "host.json")
    after = common.candidate_digest(tree)
    assert report["status"] == "PASS"
    assert report["physical_android_validated"] is False
    assert before == after
    assert not list(tree.rglob("*.pyc"))


def physical_record(kind: str, digest: str) -> dict[str, object]:
    base: dict[str, object] = {
        "format": "automation-rc4-physical-evidence-v1",
        "evidence_type": kind,
        "status": "PASS",
        "candidate_tree_root_sha256": digest,
        "private_keys_exported": False,
    }
    if kind in {"ANDROID_VALIDATION", "ENDURANCE_VALIDATION", "DEVICE_SYNC_VALIDATION"}:
        base.update(
            {
                "platform": "android-termux",
                "android_detected": True,
                "termux_detected": True,
                "physical_android_validated": True,
                "attestation_verified": True,
            }
        )
    if kind == "ENDURANCE_VALIDATION":
        base.update({"successful_samples": 60, "elapsed_seconds": 3600, "unrecovered_jobs": 0})
    if kind == "DEVICE_SYNC_VALIDATION":
        base.update({"signed_bundle_verified": True, "peer_key_pinned": True})
    if kind == "RECOVERY_DRILL":
        base.update({"restore_verified": True, "rollback_verified": True})
    return base


def test_evidence_gate_requires_candidate_bound_physical_attestations(tmp_path: Path) -> None:
    tree = make_candidate(tmp_path)
    digest = common.candidate_digest(tree)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    for kind in sorted(evidence.REQUIRED):
        (evidence_dir / f"{kind}.json").write_text(
            json.dumps(physical_record(kind, digest)),
            encoding="utf-8",
        )
    report = evidence.gate(tree, evidence_dir)
    assert report["status"] == "PASS"
    assert report["promotion_performed"] is False


def test_evidence_gate_blocks_raw_unattested_device_json(tmp_path: Path) -> None:
    tree = make_candidate(tmp_path)
    digest = common.candidate_digest(tree)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    for kind in sorted(evidence.REQUIRED):
        record = physical_record(kind, digest)
        if kind == "ANDROID_VALIDATION":
            record["attestation_verified"] = False
        (evidence_dir / f"{kind}.json").write_text(json.dumps(record), encoding="utf-8")
    report = evidence.gate(tree, evidence_dir)
    assert report["status"] == "BLOCK"
    assert any("attestation" in error for error in report["errors"])


def test_custom_resolution_is_hash_bound(tmp_path: Path) -> None:
    analysis = tmp_path / "analysis"
    write(analysis / "schema10" / "tree" / "x.txt", "left")
    write(analysis / "ga" / "tree" / "x.txt", "right")
    (analysis / "reports").mkdir(parents=True)
    queue = {
        "format": "automation-rc4-review-queue-successor-v1",
        "changed_common": [{"path": "x.txt"}],
        "common_same": [],
        "schema10_only": [],
        "ga_only": [],
    }
    (analysis / "reports" / "RC4_REVIEW_QUEUE.json").write_text(
        json.dumps(queue), encoding="utf-8"
    )
    custom = tmp_path / "custom.txt"
    custom.write_text("reviewed custom", encoding="utf-8")
    decisions = {
        "format": "automation-rc4-merge-decisions-v1",
        "target_release": "1.0.0-rc4-converged",
        "target_schema": 10,
        "reviewed_by": "Reviewer",
        "reviewed_at": "2026-08-11T12:00:00Z",
        "changed_common": {
            "x.txt": {
                "resolution": "custom",
                "rationale": "Explicit synthetic merge.",
                "tests": ["custom merge regression"],
                "custom_source_path": str(custom),
                "custom_sha256": "0" * 64,
            }
        },
    }
    decisions_path = tmp_path / "bad-decisions.json"
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
    with pytest.raises(ValueError, match="identity verification failed"):
        constructor.build(analysis, decisions_path, tmp_path / "out")
