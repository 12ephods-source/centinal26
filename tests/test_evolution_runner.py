from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from centinal26.evolution_sandbox import EvolutionDockerEvaluator
from centinal26.hard_sandbox import SandboxLimits, SandboxUnavailable, verify_result_hash


def _live_evaluator() -> EvolutionDockerEvaluator:
    image = os.environ.get(
        "CENTINAL26_SANDBOX_IMAGE", "centinal26-evolution-validator:local"
    )
    instance = EvolutionDockerEvaluator(image=image)
    required = os.environ.get("CENTINAL26_EVOLUTION_SANDBOX_REQUIRED") == "1"
    if shutil.which("docker") is None:
        if required:
            pytest.fail("Docker is required by this integration gate")
        pytest.skip("Docker is not installed")
    try:
        instance.probe()
    except SandboxUnavailable as error:
        if required:
            pytest.fail(str(error))
        pytest.skip(str(error))
    return instance


def test_validator_image_executes_candidate_tests(tmp_path: Path) -> None:
    instance = _live_evaluator()
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

    result = instance.evaluate(
        root,
        candidate_commit="a" * 40,
        goal_digest="b" * 64,
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
    assert result.sandbox_image_id.startswith("sha256:")
    assert verify_result_hash(result)


def test_supported_entrypoint_uses_sandboxed_wrapper() -> None:
    root = Path(__file__).resolve().parents[1]
    runner = (root / "scripts" / "run-controlled-evolution.sh").read_text(encoding="utf-8")
    wrapper = (root / "scripts" / "controlled_evolution_sandboxed.py").read_text(
        encoding="utf-8"
    )

    assert "controlled_evolution_sandboxed.py" in runner
    assert "Docker hard isolation is required" in runner
    assert "There is no host validator fallback" in runner
    assert 'controlled_evolution_loop.py" --repo' not in runner
    assert wrapper.index("candidate_commit = loop.commit_candidate") < wrapper.index(
        "validation_passed, score, validation_results = evaluate_with_commit"
    )
    assert "host fallback is disabled" in wrapper
    assert "runner.evaluate(" in wrapper
