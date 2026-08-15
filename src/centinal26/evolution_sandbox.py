from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path

from .hard_sandbox import (
    DockerEvaluator,
    SandboxLimits,
    SandboxUnavailable,
)


class EvolutionDockerEvaluator(DockerEvaluator):
    """Docker evaluator backed entirely by a dedicated validator image.

    The candidate tree is the only host filesystem input and is mounted
    read-only at /src. Validator tooling must already exist in the configured
    content-addressed container image; host runtime directories are not bound
    into candidate execution.
    """

    def _mount_arguments(self, candidate_root: Path) -> list[str]:
        source_text = str(candidate_root)
        if "," in source_text:
            raise ValueError("sandbox source paths may not contain commas")
        return [
            "--mount",
            f"type=bind,src={source_text},dst=/src,readonly",
        ]

    def _base_command(
        self, candidate_root: Path, limits: SandboxLimits, container_name: str
    ) -> list[str]:
        command = super()._base_command(candidate_root, limits, container_name)
        # DockerEvaluator places the image as the final argument. Inject only
        # deterministic evaluator variables before it; no caller environment is inherited.
        image = command.pop()
        command.extend(
            [
                "--env",
                "PATH=/usr/local/bin:/usr/bin:/bin",
                "--env",
                "PYTHONPATH=/src/src",
                "--env",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
                "--env",
                "CENTINAL26_EVOLUTION_EVALUATION=1",
                image,
            ]
        )
        return command

    def probe(self) -> None:
        """Require an executable validator image before candidate execution."""
        self.image_id()
        limits = SandboxLimits(
            cpu_seconds=5,
            wall_seconds=20,
            memory_bytes=128 * 1024 * 1024,
            processes=16,
        )
        container_name = f"centinal26-evolution-probe-{uuid.uuid4().hex[:16]}"
        with tempfile.TemporaryDirectory(prefix="centinal26-evolution-probe-") as raw_probe:
            command = self._base_command(Path(raw_probe), limits, container_name) + [
                "/usr/local/bin/python",
                "-c",
                "import pytest,sys; assert sys.version_info[:2] == (3,13); print(pytest.__version__)",
            ]
            try:
                result = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    env={},
                    check=False,
                    timeout=25,
                )
            except subprocess.TimeoutExpired as error:
                self._force_remove(container_name)
                raise SandboxUnavailable("evolution sandbox probe timed out") from error

        if result.returncode != 0:
            self._force_remove(container_name)
            detail = result.stderr.decode("utf-8", errors="replace")[:400]
            raise SandboxUnavailable(f"evolution sandbox probe failed: {detail}")
