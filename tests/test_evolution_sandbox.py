from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from centinal26.evolution_sandbox import evaluate_in_hard_sandbox
from centinal26.hard_sandbox import SandboxUnavailable, verify_result_hash

ROOT = Path(__file__).resolve().parents[1]


def _require_live_sandbox() -> None:
    required = os.environ.get("CENTINAL26_HARD_SANDBOX_REQUIRED") == "1"
    if shutil.which("docker") is None:
        if required:
            pytest.fail("docker is required by the hard-sandbox CI gate")
        pytest.skip("docker is not installed")
    image = os.environ.get("CENTINAL26_SANDBOX_IMAGE", "centinal26-sandbox-root:local")
    probe = __import__("subprocess").run(
        ["docker", "image", "inspect", image],
        stdin=__import__("subprocess").DEVNULL,
        stdout=__import__("subprocess").DEVNULL,
        stderr=__import__("subprocess").DEVNULL,
        check=False,
    )
    if probe.returncode != 0:
        if required:
            pytest.fail("hard-sandbox image is required but unavailable")
        pytest.skip("hard-sandbox image is not prepared")


def test_supported_launcher_uses_hard_runner_and_has_no_legacy_direct_path() -> None:
    launcher = (ROOT / "scripts/run-controlled-evolution.sh").read_text(encoding="utf-8")
    hard_runner = (ROOT / "scripts/controlled_evolution_hard.py").read_text(encoding="utf-8")

    assert "controlled_evolution_hard.py" in launcher
    assert 'python "$ROOT/scripts/controlled_evolution_loop.py"' not in launcher
    assert "host execution fallback is disabled" in launcher
    assert "evaluate_in_hard_sandbox" in hard_runner
    assert "host_execution_fallback" in hard_runner


def test_hard_runner_protects_its_security_boundary_from_candidates() -> None:
    hard_runner = (ROOT / "scripts/controlled_evolution_hard.py").read_text(encoding="utf-8")
    for protected in (
        "src/centinal26/hard_sandbox.py",
        "src/centinal26/evolution_sandbox.py",
        "scripts/controlled_evolution_hard.py",
        "scripts/controlled_evolution_loop.py",
        "scripts/run-controlled-evolution.sh",
    ):
        assert protected in hard_runner


def test_locked_validators_execute_inside_hard_sandbox(tmp_path: Path) -> None:
    _require_live_sandbox()
    candidate = tmp_path / "candidate"
    (candidate / "src/demo").mkdir(parents=True)
    (candidate / "tests").mkdir()
    (candidate / "scripts").mkdir()
    (candidate / "src/demo/__init__.py").write_text("VALUE = 42\n", encoding="utf-8")
    (candidate / "tests/test_goal.py").write_text(
        "from demo import VALUE\n\ndef test_value():\n    assert VALUE == 42\n",
        encoding="utf-8",
    )
    (candidate / "tests/validate_repository.py").write_text(
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    (candidate / "scripts/check.py").write_text("VALUE = 1\n", encoding="utf-8")

    try:
        passed, score, results = evaluate_in_hard_sandbox(
            candidate,
            candidate_commit="a" * 40,
            goal_digest="b" * 64,
            goal_tests=("tests/test_goal.py",),
        )
    except SandboxUnavailable as error:
        if os.environ.get("CENTINAL26_HARD_SANDBOX_REQUIRED") == "1":
            pytest.fail(str(error))
        pytest.skip(str(error))

    assert passed is True
    assert score == 1.0
    assert [item["name"] for item in results] == [
        "goal_tests",
        "repository_invariants",
        "compile",
    ]
    assert all(item["passed"] for item in results)
    assert all(item["sandbox_backend"] == "docker" for item in results)
    assert all(item["sandbox_image_id"].startswith("sha256:") for item in results)
    assert all(len(item["evidence_sha256"]) == 64 for item in results)


def test_evidence_hash_verifier_rejects_missing_identity() -> None:
    assert verify_result_hash({}) is False
