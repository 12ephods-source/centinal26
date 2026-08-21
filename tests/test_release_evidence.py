import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_builder(output: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, "scripts/build_release_evidence.py", "--output", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert len(completed.stdout.strip()) == 64
    return json.loads(output.read_text(encoding="utf-8"))


def test_release_evidence_is_deterministic_for_same_commit(tmp_path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    one = run_builder(first)
    two = run_builder(second)
    assert one == two
    assert first.read_bytes() == second.read_bytes()
    assert one["manifest_sha256"] == two["manifest_sha256"]


def test_release_evidence_contains_canonical_ledgers_and_no_physical_inference(tmp_path) -> None:
    output = tmp_path / "release.json"
    manifest = run_builder(output)
    tracked = {entry["path"] for entry in manifest["source_tree"]["files"]}
    for path in (
        "automation/PROJECT_STATE.json",
        "releases/RELEASE_CONTRACT.json",
        "releases/AUTHORITY_MATRIX.json",
        "releases/RELEASE_ENGINEERING_CONTRACT.json",
        "releases/COMPATIBILITY_MATRIX.json",
        "releases/DEPRECATION_REGISTRY.json",
    ):
        assert path in tracked
    assert manifest["evidence_boundaries"]["host_manifest_generated"] is True
    assert manifest["evidence_boundaries"]["device_validation_inferred"] is False
    assert manifest["evidence_boundaries"]["persistence_validation_inferred"] is False
    assert manifest["evidence_boundaries"]["recovery_validation_inferred"] is False


def test_release_engineering_validator_accepts_generated_manifest(tmp_path) -> None:
    output = tmp_path / "release.json"
    run_builder(output)
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_release_engineering.py",
            "--evidence",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.stdout.startswith("PASS:")
