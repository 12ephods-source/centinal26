"""Fail-closed source-enumeration gate for the nonsupersymmetric SO(10) 126_H self-sector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_QUADRATIC = ["(Sigma Sigma*)_0"]
EXPECTED_HERMITIAN_QUARTIC = [
    "(Sigma Sigma*)_0 (Sigma Sigma*)_0",
    "(Sigma Sigma*)_2 (Sigma Sigma*)_2",
    "(Sigma Sigma*)_4 (Sigma Sigma*)_4",
    "(Sigma Sigma*)_4_prime (Sigma Sigma*)_4_prime",
]
EXPECTED_COMPLEX_QUARTIC = ["(Sigma Sigma)_2 (Sigma Sigma)_2 + h.c."]
EXPECTED_SOURCE = "2304.14227"


def evaluate(contract: dict) -> dict:
    sector = contract.get("self_sector", {})
    checks = {
        "schema": contract.get("schema") == "FTOE-SCALAR-ACTION-126-SELF-v12",
        "primary_source": contract.get("primary_source", {}).get("arxiv") == EXPECTED_SOURCE,
        "quadratic_basis": sector.get("quadratic_invariants") == EXPECTED_QUADRATIC,
        "cubic_absent": sector.get("cubic_invariants") == [],
        "cubic_absence_source_verified": sector.get("cubic_absence_source_verified") is True,
        "hermitian_quartic_basis": (
            sector.get("hermitian_quartic_invariants") == EXPECTED_HERMITIAN_QUARTIC
        ),
        "complex_quartic_basis": sector.get("complex_quartic_invariants") == EXPECTED_COMPLEX_QUARTIC,
        "real_quartic_coupling_count": sector.get("real_quartic_coupling_count") == 4,
        "complex_quartic_coupling_count": sector.get("complex_quartic_coupling_count") == 1,
        "source_completeness_cross_check": sector.get("source_completeness_cross_check") is True,
        "full_action_fail_closed": contract.get("full_action_gate") == "NOT_COMPLETE",
        "no_downstream_retuning": contract.get("no_downstream_retuning") is True,
    }
    passed = all(checks.values())
    return {
        "schema": "FTOE-SCALAR-ACTION-126-SELF-GATE-v12",
        "checks": checks,
        "execution_pass": passed,
        "claim_status": (
            "PARTIAL_ACTION_126_SELF_SECTOR_SOURCE_ENUMERATED"
            if passed
            else "SOURCE_ENUMERATION_FAIL"
        ),
        "scientific_status": "REVIEW" if passed else "FAIL",
        "full_action_gate": "NOT_COMPLETE",
        "scope_limit": (
            "Only the 126_H self-sector is adjudicated; mixed sectors and downstream vacuum, "
            "spectrum, threshold, and publication claims remain unresolved."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    result = evaluate(contract)
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")
    raise SystemExit(0 if result["execution_pass"] else 1)


if __name__ == "__main__":
    main()
