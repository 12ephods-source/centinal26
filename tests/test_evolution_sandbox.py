from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from centinal26.evolution_sandbox import EvolutionDockerEvaluator
from centinal26.hard_sandbox import SandboxLimits, SandboxUnavailable, verify_result_hash

COMMIT = "a" * 40
GOAL = "b" * 64


def _evaluator() -> EvolutionDockerEvaluator:
    image = os.environ.get(
        "CENTINAL26_SANDBOX_IMAGE", "centinal26-evolution-validator:local"
    )
    evaluator = EvolutionDockerEvaluator(image=image)
    required = os.environ.get("CENTINAL26_EVOLUTION_SANDBOX_REQUIRED") == "1"
    if shutil.which("docker") is None:
        if required:
            pytest.fail("Docker is required by the evolution-sandbox integration gate")
        pytest.skip("Docker is not installed")
    try:
        evaluator.probe()
    except SandboxUnavailable as error:
        if required:
            pytest.fail(str(error))
        pytest.skip(str(error))
    return evaluator


def test_validator_image_runs_candidate_pytest_read_only(tmp_path: Path) -> None:
    evaluator = _evaluator()
    root = tmp_path / "candidate"
    package = root / "src" / "demo_candidate"
    tests = root / "tests"
    package.mkdir(parents=True)
    tests.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")
    (tests / "test_demo.py").write_text(
        "from demo_candidate import VALUE\n\ndef test_value():\n    assert VALUE == 42\n",
        encoding="utf-8",
    )

    result = evaluator.evaluate(
        root,
        candidate_commit=COMMIT,
        goal_digest=GOAL,
        command=["/usr/local/bin/python", "-m", "pytest", "-q", "tests/test_demo.py"],
        validator_versions={
            "adapter": "centinal26-evolution-docker/1",
            "python": "3.13",
            "pytest": "9.1.1",
            "validator": "integration-fixture",
        },
        limits=SandboxLimits(
            cpu_seconds=20,
            wall_seconds=30,
            memory_bytes=256 * 1024 * 1024,
            processes=32,
        ),
    )

    assert result.exit_code == 0, result.stderr
    assert "1 passed" in result.stdout
    assert result.isolation["network"] == "none"
    assert result.isolation["source_mount"] == "read_only"
    assert result.isolation["host_execution_fallback"] is False
    assert result.sandbox_image_id.startswith("sha256:")
    assert verify_result_hash(result)
    assert not (root / ".pytest_cache").exists()


def test_supported_runner_requires_sandboxed_wrapper() -> None:
    root = Path(__file__).resolve().parents[1]
    runner = (root / "scripts" / "run-controlled-evolution.sh").read_text(encoding="utf-8")

    assert "controlled_evolution_sandboxed.py" in runner
    assert "Docker hard isolation is required" in runner
    assert "There is no host validator fallback" in runner
    assert 'controlled_evolution_loop.py" --repo' not in runner


def test_sandboxed_wrapper_commits_candidate_before_validation() -> None:
    root = Path(__file__).resolve().parents[1]
    wrapper = (root / "scripts" / "controlled_evolution_sandboxed.py").read_text(
        encoding="utf-8"
    )
    commit_index = wrapper.index("candidate_commit = loop.commit_candidate")
    evaluate_index = wrapper.index("validation_passed, score, validation_results = evaluate_with_commit")

    assert commit_index < evaluate_index
    assert "host fallback is disabled" in wrapper
    assert "runner.evaluate(" in wrapper
