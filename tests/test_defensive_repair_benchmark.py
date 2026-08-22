import json

import pytest

from frost_core.defensive_repair_benchmark import (
    REPAIRED_SOURCE,
    VULNERABLE_SOURCE,
    candidate_repair,
    independently_verify,
    reproduce,
    run_benchmark,
)


def _evidence(original: str, repaired: str, patch: str) -> tuple[str, dict]:
    result = independently_verify(original, repaired, patch)
    return result.status, json.loads(result.evidence_json)


def test_known_ground_truth_reproduces_before_repair() -> None:
    result = reproduce(VULNERABLE_SOURCE)
    assert result == {"reproduced": True, "failure": "ZeroDivisionError"}


def test_candidate_repair_clears_reproducer_and_preserves_regressions() -> None:
    repair = candidate_repair(VULNERABLE_SOURCE)
    assert repair["source"] == REPAIRED_SOURCE
    status, evidence = _evidence(VULNERABLE_SOURCE, repair["source"], repair["patch"])
    assert status == "INDEPENDENTLY_VERIFIED"
    assert evidence["checks"]["original_reproduced"] is True
    assert evidence["checks"]["reproducer_cleared"] is True
    assert evidence["checks"]["regressions_pass"] is True
    assert all(evidence["regressions"].values())


def test_verifier_rejects_tampered_patch() -> None:
    repair = candidate_repair(VULNERABLE_SOURCE)
    status, evidence = _evidence(
        VULNERABLE_SOURCE,
        repair["source"],
        repair["patch"] + "# tampered\n",
    )
    assert status == "VERIFICATION_FAILED"
    assert evidence["checks"]["patch_identity"] is False


def test_verifier_rejects_altered_original_source() -> None:
    repair = candidate_repair(VULNERABLE_SOURCE)
    altered = VULNERABLE_SOURCE + "# altered\n"
    with pytest.raises(ValueError, match="exact pinned fixture"):
        independently_verify(altered, repair["source"], repair["patch"])


def test_verifier_rejects_altered_repair_source() -> None:
    repair = candidate_repair(VULNERABLE_SOURCE)
    altered = repair["source"] + "# altered\n"
    status, evidence = _evidence(VULNERABLE_SOURCE, altered, repair["patch"])
    assert status == "VERIFICATION_FAILED"
    assert evidence["checks"]["repair_identity"] is False


def test_verifier_rejects_regression_inducing_repair() -> None:
    repair = candidate_repair(VULNERABLE_SOURCE)
    bad_repair = """def mean(values):\n    if not values:\n        return 0.0\n    return 999.0\n"""
    status, evidence = _evidence(VULNERABLE_SOURCE, bad_repair, repair["patch"])
    assert status == "VERIFICATION_FAILED"
    assert evidence["checks"]["repair_identity"] is False
    assert evidence["checks"]["regressions_pass"] is False


def test_candidate_repair_rejects_unpinned_input() -> None:
    with pytest.raises(ValueError, match="exact pinned fixture"):
        candidate_repair(VULNERABLE_SOURCE + "# mutation\n")


def test_evidence_is_deterministic_for_identical_inputs() -> None:
    first = run_benchmark()
    second = run_benchmark()
    assert first == second
    assert first.evidence_json == second.evidence_json


def test_evidence_hashes_bind_source_repair_and_patch() -> None:
    result = run_benchmark()
    evidence = json.loads(result.evidence_json)
    assert len(evidence["source_sha256"]) == 64
    assert len(evidence["repair_sha256"]) == 64
    assert len(evidence["patch_sha256"]) == 64
    assert len({evidence["source_sha256"], evidence["repair_sha256"], evidence["patch_sha256"]}) == 3


def test_full_benchmark() -> None:
    result = run_benchmark()
    assert result.status == "INDEPENDENTLY_VERIFIED"
