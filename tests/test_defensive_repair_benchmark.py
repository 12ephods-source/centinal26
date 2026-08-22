import json

from frost_core.defensive_repair_benchmark import (
    REPAIRED_SOURCE,
    VULNERABLE_SOURCE,
    candidate_repair,
    independently_verify,
    reproduce,
    run_benchmark,
)


def test_known_ground_truth_reproduces_before_repair() -> None:
    result = reproduce(VULNERABLE_SOURCE)
    assert result == {"reproduced": True, "failure": "ZeroDivisionError"}


def test_candidate_repair_clears_reproducer_and_preserves_regressions() -> None:
    repair = candidate_repair(VULNERABLE_SOURCE)
    assert repair["source"] == REPAIRED_SOURCE
    result = independently_verify(VULNERABLE_SOURCE, repair["source"], repair["patch"])
    evidence = json.loads(result.evidence_json)
    assert result.status == "INDEPENDENTLY_VERIFIED"
    assert evidence["checks"]["original_reproduced"] is True
    assert evidence["checks"]["reproducer_cleared"] is True
    assert evidence["checks"]["regressions_pass"] is True
    assert all(evidence["regressions"].values())


def test_verifier_rejects_tampered_patch() -> None:
    repair = candidate_repair(VULNERABLE_SOURCE)
    result = independently_verify(VULNERABLE_SOURCE, repair["source"], repair["patch"] + "# tampered\n")
    evidence = json.loads(result.evidence_json)
    assert result.status == "VERIFICATION_FAILED"
    assert evidence["checks"]["patch_identity"] is False


def test_full_benchmark() -> None:
    result = run_benchmark()
    assert result.status == "INDEPENDENTLY_VERIFIED"
