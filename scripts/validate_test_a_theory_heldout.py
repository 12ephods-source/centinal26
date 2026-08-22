from __future__ import annotations

import json
from pathlib import Path

from centinal26.test_a_theory import evaluate_model

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "validation" / "test_a_theory" / "heldout_cases.json"


def main() -> int:
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    if payload.get("schema") != "test-a-theory/host-heldout-v1":
        raise SystemExit("invalid heldout schema")
    if payload.get("frozen_before_candidate_qualification") is not True:
        raise SystemExit("heldout cases are not frozen")
    failures: list[str] = []
    for case in payload.get("cases", []):
        report = evaluate_model(case["model"])
        if report.verdict != case["expected_verdict"]:
            failures.append(
                f"{case['case_id']}: expected {case['expected_verdict']} got {report.verdict}"
            )
    if failures:
        print(json.dumps({"status": "FAIL", "failures": failures}, sort_keys=True))
        return 1
    print(json.dumps({"status": "PASS_HOST_HELDOUT_FIXTURES", "cases": len(payload["cases"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
