from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .intent_execution import CapabilityRegistry

Json = dict[str, Any]


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    timeout_s: int = 30


class BoundedLocalExecutor:
    """Execute only pre-registered argv vectors; never accepts shell source."""

    def __init__(self, specs: dict[str, CommandSpec]) -> None:
        self.specs = dict(specs)

    def run(self, name: str) -> Json:
        try:
            spec = self.specs[name]
        except KeyError as exc:
            raise ValueError(f"unknown bounded operation: {name}") from exc
        completed = subprocess.run(
            spec.argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=spec.timeout_s,
            shell=False,
        )
        return {
            "operation": name,
            "argv": list(spec.argv),
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-16384:],
            "stderr": completed.stderr[-16384:],
        }


def _verify_zero_exit(payload: Json, output: Json) -> bool:
    del payload
    return output.get("exit_code") == 0


def _verify_sha256(payload: Json, output: Json) -> bool:
    path = Path(str(payload["path"])).expanduser().resolve()
    if not path.is_file():
        return False
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return output.get("sha256") == digest


def register_physical_capabilities(
    registry: CapabilityRegistry,
    *,
    executor: BoundedLocalExecutor | None = None,
) -> None:
    """Register the minimal device-safe capability surface.

    These capabilities are deliberately diagnostic/read-only. Consequential
    operations require separate authorization policy and are not registered here.
    """
    local = executor or BoundedLocalExecutor(
        {
            "device.python_version": CommandSpec(("python", "--version"), 10),
            "device.uname": CommandSpec(("uname", "-a"), 10),
        }
    )

    registry.register(
        "device.python_version",
        lambda payload: local.run("device.python_version"),
        _verify_zero_exit,
    )
    registry.register(
        "device.uname",
        lambda payload: local.run("device.uname"),
        _verify_zero_exit,
    )

    def sha256_file(payload: Json) -> Json:
        path = Path(str(payload["path"])).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    registry.register("device.sha256_file", sha256_file, _verify_sha256)
