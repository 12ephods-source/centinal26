from __future__ import annotations

import importlib.metadata
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hard_sandbox import DockerEvaluator, SandboxLimits, SandboxResult, SandboxUnavailable

_COMPILE_CHECK = """
from pathlib import Path
failed = []
for root in (Path('src'), Path('scripts')):
    if not root.exists():
        continue
    for path in sorted(root.rglob('*.py')):
        try:
            compile(path.read_text(encoding='utf-8'), str(path), 'exec')
        except Exception as error:
            failed.append(f'{path}: {type(error).__name__}: {error}')
if failed:
    raise SystemExit('\n'.join(failed))
""".strip()


@dataclass(frozen=True)
class ValidatorSpec:
    name: str
    command: tuple[str, ...]
    wall_seconds: float
    cpu_seconds: int
    weight: float


class _RuntimeDockerEvaluator(DockerEvaluator):
    """Docker evaluator with one exact read-only Python runtime mount."""

    def __init__(self, runtime_prefix: Path, python_executable: Path):
        super().__init__()
        self.runtime_prefix = runtime_prefix.expanduser().absolute()
        self.python_executable = python_executable.expanduser().absolute()
        if not self.runtime_prefix.is_dir():
            raise SandboxUnavailable(f"Python runtime prefix is unavailable: {self.runtime_prefix}")
        if not self.python_executable.is_file():
            raise SandboxUnavailable(
                f"Python runtime executable is unavailable: {self.python_executable}"
            )
        under_runtime = self.python_executable.is_relative_to(self.runtime_prefix)
        under_system = self.python_executable.is_relative_to(Path("/usr"))
        if not under_runtime and not under_system:
            raise SandboxUnavailable(
                "Python executable must be inside the exact runtime prefix or /usr"
            )

    def _mount_arguments(self, candidate_root: Path) -> list[str]:
        arguments = super()._mount_arguments(candidate_root)
        if not self.runtime_prefix.is_relative_to(Path("/usr")):
            source = str(self.runtime_prefix)
            if "," in source:
                raise ValueError("sandbox runtime path may not contain commas")
            arguments.extend(
                [
                    "--mount",
                    f"type=bind,src={source},dst={source},readonly",
                ]
            )
        return arguments

    def _base_command(
        self, candidate_root: Path, limits: SandboxLimits, container_name: str
    ) -> list[str]:
        command = super()._base_command(candidate_root, limits, container_name)
        image = command.pop()
        command.extend(
            [
                "--env",
                "PYTHONPATH=/src/src",
                "--env",
                "PYTHONPYCACHEPREFIX=/tmp/pycache",
                "--env",
                "XDG_CACHE_HOME=/tmp/cache",
                "--env",
                "CENTINAL26_EVOLUTION_EVALUATION=1",
                image,
            ]
        )
        return command


def validator_versions() -> dict[str, str]:
    try:
        pytest_version = importlib.metadata.version("pytest")
    except importlib.metadata.PackageNotFoundError as error:
        raise SandboxUnavailable("pytest is unavailable in the validator runtime") from error
    return {
        "python": sys.version.split()[0],
        "pytest": pytest_version,
        "evolution-sandbox-contract": "1",
    }


def validator_specs(goal_tests: tuple[str, ...], python_executable: str) -> tuple[ValidatorSpec, ...]:
    return (
        ValidatorSpec(
            name="goal_tests",
            command=(
                python_executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                *goal_tests,
            ),
            wall_seconds=300,
            cpu_seconds=120,
            weight=0.70,
        ),
        ValidatorSpec(
            name="repository_invariants",
            command=(python_executable, "tests/validate_repository.py"),
            wall_seconds=180,
            cpu_seconds=60,
            weight=0.20,
        ),
        ValidatorSpec(
            name="compile",
            command=(python_executable, "-c", _COMPILE_CHECK),
            wall_seconds=180,
            cpu_seconds=60,
            weight=0.10,
        ),
    )


def _limits(spec: ValidatorSpec) -> SandboxLimits:
    return SandboxLimits(
        cpu_seconds=spec.cpu_seconds,
        memory_bytes=1024 * 1024 * 1024,
        processes=64,
        wall_seconds=spec.wall_seconds,
        output_bytes=1024 * 1024,
        open_files=128,
        cpus=2.0,
        tmp_bytes=128 * 1024 * 1024,
    )


def _result_record(spec: ValidatorSpec, result: SandboxResult) -> dict[str, Any]:
    passed = (
        result.exit_code == 0
        and not result.timed_out
        and not result.output_limited
    )
    output = (result.stdout + result.stderr)[-8000:]
    return {
        "name": spec.name,
        "passed": passed,
        "output": output,
        "sandbox_backend": result.sandbox_backend,
        "sandbox_image_id": result.sandbox_image_id,
        "source_digest": result.source_digest,
        "evidence_sha256": result.evidence_sha256,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "output_limited": result.output_limited,
    }


def evaluate_in_hard_sandbox(
    candidate_root: Path,
    *,
    candidate_commit: str,
    goal_digest: str,
    goal_tests: tuple[str, ...],
    runtime_prefix: Path | None = None,
    python_executable: Path | None = None,
) -> tuple[bool, float, list[dict[str, Any]]]:
    """Run the supported controlled-evolution validators only inside the hard sandbox."""
    prefix = runtime_prefix or Path(sys.prefix)
    executable = python_executable or Path(sys.executable)
    evaluator = _RuntimeDockerEvaluator(prefix, executable)
    versions = validator_versions()
    specs = validator_specs(goal_tests, str(executable.absolute()))

    results: list[dict[str, Any]] = []
    score = 0.0
    passed = True
    for spec in specs:
        result = evaluator.evaluate(
            candidate_root,
            candidate_commit=candidate_commit,
            goal_digest=goal_digest,
            command=list(spec.command),
            validator_versions=versions,
            limits=_limits(spec),
        )
        record = _result_record(spec, result)
        results.append(record)
        if record["passed"]:
            score += spec.weight
        else:
            passed = False
    return passed, round(score, 6), results
