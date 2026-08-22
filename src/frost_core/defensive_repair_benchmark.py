from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from difflib import unified_diff

FIXTURE_ID = "known-ground-truth-empty-mean-v1"
VULNERABLE_SOURCE = """def mean(values):\n    return sum(values) / len(values)\n"""
REPAIRED_SOURCE = """def mean(values):\n    if not values:\n        return 0.0\n    return sum(values) / len(values)\n"""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_mean(source: str):
    tree = ast.parse(source)
    code = compile(tree, f"<{FIXTURE_ID}>", "exec")
    namespace: dict[str, object] = {"__builtins__": {"sum": sum, "len": len}}
    exec(code, namespace)  # noqa: S102 - fixed, repository-owned benchmark fixture only
    return namespace["mean"]


def _regression_results(source: str) -> dict[str, bool]:
    mean = _load_mean(source)
    return {
        "empty_returns_zero": mean([]) == 0.0,
        "singleton": mean([4]) == 4.0,
        "ordinary_mean": mean([1, 2, 3]) == 2.0,
    }


def reproduce(source: str) -> dict[str, object]:
    mean = _load_mean(source)
    try:
        mean([])
    except ZeroDivisionError:
        return {"reproduced": True, "failure": "ZeroDivisionError"}
    return {"reproduced": False, "failure": None}


def candidate_repair(source: str) -> dict[str, str]:
    if source != VULNERABLE_SOURCE:
        raise ValueError("benchmark repair only accepts the exact pinned fixture source")
    patch = "".join(
        unified_diff(
            source.splitlines(keepends=True),
            REPAIRED_SOURCE.splitlines(keepends=True),
            fromfile="fixture.py",
            tofile="fixture.py",
        )
    )
    return {"source": REPAIRED_SOURCE, "patch": patch}


@dataclass(frozen=True)
class VerificationResult:
    status: str
    evidence_json: str


def independently_verify(original: str, repaired: str, patch: str) -> VerificationResult:
    original_repro = reproduce(original)
    repaired_repro = reproduce(repaired)
    regressions = _regression_results(repaired)
    expected_patch = candidate_repair(original)["patch"]

    checks = {
        "fixture_identity": _sha256(original) == _sha256(VULNERABLE_SOURCE),
        "original_reproduced": original_repro["reproduced"] is True,
        "patch_identity": patch == expected_patch,
        "repair_identity": _sha256(repaired) == _sha256(REPAIRED_SOURCE),
        "reproducer_cleared": repaired_repro["reproduced"] is False,
        "regressions_pass": all(regressions.values()),
    }
    status = "INDEPENDENTLY_VERIFIED" if all(checks.values()) else "VERIFICATION_FAILED"
    evidence = {
        "fixture_id": FIXTURE_ID,
        "authority": "repository-owned known-ground-truth fixture only",
        "source_sha256": _sha256(original),
        "repair_sha256": _sha256(repaired),
        "patch_sha256": _sha256(patch),
        "checks": checks,
        "regressions": regressions,
        "status": status,
    }
    return VerificationResult(status=status, evidence_json=json.dumps(evidence, sort_keys=True))


def run_benchmark() -> VerificationResult:
    repair = candidate_repair(VULNERABLE_SOURCE)
    return independently_verify(VULNERABLE_SOURCE, repair["source"], repair["patch"])
