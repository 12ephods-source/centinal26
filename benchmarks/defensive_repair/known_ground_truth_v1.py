#!/usr/bin/env python3
"""Known-ground-truth defensive repair benchmark.

This is an intentionally defective local fixture, not a vulnerability scanner.
It tests Centinal26 promotion semantics: reproduce -> repair -> regression ->
independent verification.
"""
from dataclasses import dataclass
import hashlib

@dataclass(frozen=True)
class Case:
    value: str
    expected: str

CASES = (
    Case("alpha", "ALPHA"),
    Case("MiXeD", "MIXED"),
    Case("", ""),
)

def defective_normalize(value: str) -> str:
    """Known defect: lowercases when the contract requires uppercase."""
    return value.lower()

def candidate_repair(value: str) -> str:
    return value.upper()

def reproduce() -> bool:
    return any(defective_normalize(c.value) != c.expected for c in CASES)

def regression() -> bool:
    return all(candidate_repair(c.value) == c.expected for c in CASES)

def independent_verify() -> dict:
    # Verifier consumes only fixture contract + candidate behavior; it does not
    # trust a generator's success claim.
    reproduced = reproduce()
    repaired = regression()
    payload = "\n".join(f"{c.value!r}->{candidate_repair(c.value)!r}" for c in CASES)
    return {
        "fixture": "known_ground_truth_v1",
        "reproduced": reproduced,
        "regression_pass": repaired,
        "independently_verified": reproduced and repaired,
        "evidence_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }

if __name__ == "__main__":
    result = independent_verify()
    assert result["reproduced"] is True
    assert result["regression_pass"] is True
    assert result["independently_verified"] is True
    print(result)
