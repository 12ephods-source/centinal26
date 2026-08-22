#!/usr/bin/env python3
"""Deterministic epistemic promotion gate.

This tool does NOT determine truth. It computes an upper bound on how strongly a
claim may be represented given the recorded independent evidence and the
domain-specific validation state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

LEVELS = {
    "UNKNOWN": 0,
    "HYPOTHESIS": 1,
    "PLAUSIBLE": 2,
    "SUPPORTED": 3,
    "STRONGLY_SUPPORTED": 4,
    "ESTABLISHED_WITHIN_SCOPE": 5,
}
REVERSE = {v: k for k, v in LEVELS.items()}
VALID_DIMENSIONS = {"PASS", "FAIL", "REVIEW", "BLOCKED", "UNKNOWN", "NOT_APPLICABLE"}
EVIDENCE_WEIGHT = {
    "USER_REPORTED": 1,
    "DERIVED": 2,
    "DIRECT_SOURCE": 3,
    "REPRODUCED": 3,
    "INDEPENDENT_DIRECT": 4,
    "EMPIRICAL": 4,
    "SCIENTIFIC_TEST": 4,
}
DOMAIN_GATE = {
    "SOURCE_SEMANTICS": "source_semantics_status",
    "SOFTWARE_BEHAVIOR": "reproduction_status",
    "DEVICE_BEHAVIOR": "device_validation_status",
    "EMPIRICAL": "empirical_status",
    "SCIENTIFIC": "scientific_status",
    "HISTORICAL_EVENT": "historical_verification_status",
    "ATTRIBUTION": "attribution_status",
    "GENERAL": None,
}

class LedgerError(ValueError):
    pass


def _validate_claim(c: dict[str, Any]) -> None:
    for key in ("claim_id", "statement", "scope", "claim_kind", "current_epistemic_status", "dimensions"):
        if key not in c:
            raise LedgerError(f"{c.get('claim_id', '<unknown>')}: missing {key}")
    if c["claim_kind"] not in DOMAIN_GATE:
        raise LedgerError(f"{c['claim_id']}: unknown claim_kind {c['claim_kind']}")
    current = c["current_epistemic_status"]
    if current not in LEVELS and current != "REJECTED":
        raise LedgerError(f"{c['claim_id']}: invalid current_epistemic_status {current}")
    for name, status in c["dimensions"].items():
        if status not in VALID_DIMENSIONS:
            raise LedgerError(f"{c['claim_id']}: invalid dimension {name}={status}")
    seen = set()
    for ev in c.get("support", []) + c.get("counterevidence", []):
        if "evidence_id" not in ev or "independence_group" not in ev or "class" not in ev:
            raise LedgerError(f"{c['claim_id']}: malformed evidence")
        if ev["class"] not in EVIDENCE_WEIGHT:
            raise LedgerError(f"{c['claim_id']}: unknown evidence class {ev['class']}")
        pair = (ev["evidence_id"], ev["independence_group"])
        if pair in seen:
            raise LedgerError(f"{c['claim_id']}: duplicate evidence {pair}")
        seen.add(pair)


def _usable_support(c: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in c.get("support", []) if e.get("integrity", "UNKNOWN") in {"PASS", "NOT_APPLICABLE"}]


def _decisive_counterevidence(c: dict[str, Any]) -> bool:
    return any(
        e.get("decisive_against_promotion") is True
        and e.get("integrity", "UNKNOWN") in {"PASS", "NOT_APPLICABLE"}
        for e in c.get("counterevidence", [])
    )


def compute_ceiling(c: dict[str, Any]) -> str:
    _validate_claim(c)

    # A recorded rejection is allowed only when there is decisive counterevidence
    # or an explicit failing domain gate.
    if c["current_epistemic_status"] == "REJECTED":
        gate = DOMAIN_GATE[c["claim_kind"]]
        gate_failed = gate is not None and c["dimensions"].get(gate) == "FAIL"
        if not (_decisive_counterevidence(c) or gate_failed):
            return "INVALID_REJECTION"
        return "REJECTED"

    support = _usable_support(c)
    groups = {e["independence_group"] for e in support}
    strongest = max((EVIDENCE_WEIGHT[e["class"]] for e in support), default=0)
    contradictions = c.get("unresolved_contradictions", [])
    dims = c["dimensions"]

    ceiling = 0
    if support:
        ceiling = 2  # PLAUSIBLE
    if strongest >= 3:
        ceiling = max(ceiling, 3)  # SUPPORTED

    independent_pass = dims.get("independent_verification_status") == "PASS"
    if independent_pass and (len(groups) >= 2 or strongest >= 4):
        ceiling = max(ceiling, 4)  # STRONGLY_SUPPORTED

    gate_name = DOMAIN_GATE[c["claim_kind"]]
    gate_pass = gate_name is None or dims.get(gate_name) in {"PASS", "NOT_APPLICABLE"}
    if independent_pass and gate_pass and len(groups) >= 2 and not contradictions:
        ceiling = max(ceiling, 5)  # ESTABLISHED_WITHIN_SCOPE

    # Fatal/failing domain evidence caps the representation, regardless of provenance.
    if gate_name is not None and dims.get(gate_name) in {"FAIL", "BLOCKED"}:
        ceiling = min(ceiling, 2)
    if contradictions:
        ceiling = min(ceiling, 3)

    return REVERSE[ceiling]


def evaluate_claim(c: dict[str, Any]) -> dict[str, Any]:
    ceiling = compute_ceiling(c)
    current = c["current_epistemic_status"]
    if current == "REJECTED":
        gate_result = "PASS" if ceiling == "REJECTED" else "FAIL"
        overpromoted = False
    elif ceiling in {"REJECTED", "INVALID_REJECTION"}:
        gate_result = "FAIL"
        overpromoted = True
    else:
        overpromoted = LEVELS[current] > LEVELS[ceiling]
        gate_result = "FAIL" if overpromoted else "PASS"

    return {
        "claim_id": c["claim_id"],
        "current_epistemic_status": current,
        "promotion_ceiling": ceiling,
        "overpromoted": overpromoted,
        "gate_result": gate_result,
        "unresolved_contradictions": len(c.get("unresolved_contradictions", [])),
        "independent_support_groups": len({e["independence_group"] for e in _usable_support(c)}),
    }


def evaluate_ledger(data: dict[str, Any]) -> dict[str, Any]:
    results = [evaluate_claim(c) for c in data.get("claims", [])]
    return {
        "policy": "epistemic-integrity-v1",
        "truth_determination": "NOT_PERFORMED",
        "claim_count": len(results),
        "pass_count": sum(r["gate_result"] == "PASS" for r in results),
        "fail_count": sum(r["gate_result"] == "FAIL" for r in results),
        "results": results,
        "overall": "PASS" if all(r["gate_result"] == "PASS" for r in results) else "FAIL",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("ledger", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    data = json.loads(args.ledger.read_text(encoding="utf-8"))
    report = evaluate_ledger(data)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
