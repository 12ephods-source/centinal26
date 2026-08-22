"""Bounded adapter for the Dedupe/Organizer v2 Termux runtime.

This adapter intentionally exposes observation/reporting operations only. It does not
expose quarantine, restore, deletion, arbitrary shell commands, arbitrary arguments,
or caller-selected executables.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DedupeOrganizerAdapterError(RuntimeError):
    """Raised when an operation is outside the bounded adapter contract."""


_ALLOWED_SIMPLE = {
    "organizer.status": "status",
    "organizer.doctor": "doctor",
    "organizer.duplicates": "duplicates",
    "organizer.near_duplicates": "near-duplicates",
    "organizer.audit_verify": "audit-verify",
    "organizer.manifest": "manifest",
    "organizer.export_state": "export-state",
}


@dataclass(frozen=True)
class Invocation:
    operation: str
    argv: tuple[str, ...]


class DedupeOrganizerAdapter:
    """Translate typed Automation operations into a fixed local CLI contract."""

    def __init__(
        self,
        *,
        executable: str = "dedupe-organizer",
        allowed_scan_roots: Iterable[str | Path] = (),
        timeout_seconds: int = 120,
        max_output_bytes: int = 1_048_576,
    ) -> None:
        if not executable or "/" in executable or "\\" in executable:
            raise DedupeOrganizerAdapterError("executable must be a fixed command name")
        if timeout_seconds < 1 or timeout_seconds > 600:
            raise DedupeOrganizerAdapterError("timeout must be between 1 and 600 seconds")
        if max_output_bytes < 1 or max_output_bytes > 8_388_608:
            raise DedupeOrganizerAdapterError("max_output_bytes outside bounded range")

        self.executable = executable
        self.allowed_scan_roots = tuple(
            Path(root).expanduser().resolve() for root in allowed_scan_roots
        )
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def invocation(self, operation: str, parameters: dict[str, Any] | None = None) -> Invocation:
        parameters = dict(parameters or {})
        if operation in _ALLOWED_SIMPLE:
            if parameters:
                raise DedupeOrganizerAdapterError(
                    f"{operation} accepts no caller-supplied parameters"
                )
            return Invocation(operation, (self.executable, _ALLOWED_SIMPLE[operation]))

        if operation == "organizer.scan":
            if set(parameters) != {"path"}:
                raise DedupeOrganizerAdapterError(
                    "organizer.scan accepts exactly one parameter: path"
                )
            target = self._validated_scan_path(parameters["path"])
            return Invocation(
                operation,
                (self.executable, "scan", str(target), "--no-organize"),
            )

        raise DedupeOrganizerAdapterError(f"operation is not allowlisted: {operation}")

    def _validated_scan_path(self, raw_path: Any) -> Path:
        if not isinstance(raw_path, (str, Path)):
            raise DedupeOrganizerAdapterError("scan path must be a string or Path")
        if not self.allowed_scan_roots:
            raise DedupeOrganizerAdapterError("no scan roots are configured")

        target = Path(raw_path).expanduser().resolve()
        for root in self.allowed_scan_roots:
            if target == root or root in target.parents:
                return target
        raise DedupeOrganizerAdapterError("scan path is outside configured roots")

    def run(self, operation: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        invocation = self.invocation(operation, parameters)
        completed = subprocess.run(
            list(invocation.argv),
            shell=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        )

        stdout = completed.stdout[: self.max_output_bytes]
        stderr = completed.stderr[: self.max_output_bytes]
        truncated = (
            len(completed.stdout) > self.max_output_bytes
            or len(completed.stderr) > self.max_output_bytes
        )

        parsed: Any = None
        if stdout:
            try:
                parsed = json.loads(stdout.decode("utf-8", errors="strict"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None

        return {
            "operation": operation,
            "exit_code": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_json": parsed,
            "stdout_text": stdout.decode("utf-8", errors="replace") if parsed is None else None,
            "stderr_text": stderr.decode("utf-8", errors="replace"),
            "truncated": truncated,
        }


def supported_operations() -> tuple[str, ...]:
    return tuple(sorted((*_ALLOWED_SIMPLE.keys(), "organizer.scan")))
