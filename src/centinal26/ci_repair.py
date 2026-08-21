from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class FailureState(StrEnum):
    ACTIVE_FAILURE = "ACTIVE_FAILURE"
    SUPERSEDED_FAILURE = "SUPERSEDED_FAILURE"
    PASS_AFTER_FAILURE = "PASS_AFTER_FAILURE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class RepairKind(StrEnum):
    RUFF_SAFE = "RUFF_SAFE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class Diagnostic:
    code: str
    path: str
    line: int
    message: str


@dataclass(frozen=True)
class RepairPlan:
    state: FailureState
    kind: RepairKind
    failing_sha: str
    latest_sha: str | None
    diagnostics: tuple[Diagnostic, ...]
    validation: tuple[str, ...]
    reason: str


_RUFF = re.compile(
    r"^(?P<code>[A-Z]+\d+)\s+.*?-->\s+(?P<path>[^:\n]+):(?P<line>\d+):\d+",
    re.MULTILINE | re.DOTALL,
)
_SAFE_RUFF_CODES = frozenset({"UP035", "UP037", "SIM117", "I001"})


def parse_ruff_diagnostics(log: str) -> tuple[Diagnostic, ...]:
    found: list[Diagnostic] = []
    for match in _RUFF.finditer(log):
        code = match.group("code")
        path = match.group("path").strip()
        line = int(match.group("line"))
        first_line = log[match.start() :].splitlines()[0].strip()
        found.append(Diagnostic(code=code, path=path, line=line, message=first_line))
    return tuple(found)


def classify_failure(
    *,
    failing_sha: str,
    failing_log: str,
    latest_sha: str | None = None,
    latest_equivalent_passed: bool = False,
) -> RepairPlan:
    if latest_sha and latest_sha != failing_sha and latest_equivalent_passed:
        return RepairPlan(
            state=FailureState.SUPERSEDED_FAILURE,
            kind=RepairKind.REVIEW_REQUIRED,
            failing_sha=failing_sha,
            latest_sha=latest_sha,
            diagnostics=(),
            validation=(),
            reason="A newer equivalent lineage already passes; do not mutate source.",
        )

    diagnostics = parse_ruff_diagnostics(failing_log)
    if diagnostics and all(item.code in _SAFE_RUFF_CODES for item in diagnostics):
        paths = sorted({item.path for item in diagnostics})
        validation = tuple(f"ruff check {path}" for path in paths)
        return RepairPlan(
            state=FailureState.ACTIVE_FAILURE,
            kind=RepairKind.RUFF_SAFE,
            failing_sha=failing_sha,
            latest_sha=latest_sha,
            diagnostics=diagnostics,
            validation=validation,
            reason="All causal diagnostics are allowlisted deterministic Ruff transformations.",
        )

    return RepairPlan(
        state=FailureState.REVIEW_REQUIRED,
        kind=RepairKind.REVIEW_REQUIRED,
        failing_sha=failing_sha,
        latest_sha=latest_sha,
        diagnostics=diagnostics,
        validation=(),
        reason="Failure is not fully covered by the bounded deterministic repair allowlist.",
    )


def receipt(plan: RepairPlan, *, run_id: int, job_id: int, log_sha256: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "job_id": job_id,
        "log_sha256": log_sha256,
        "plan": asdict(plan),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def write_receipt(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
