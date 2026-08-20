"""Fail-closed source audit for the renormalizable SO(10) 210_H self-sector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate(contract: dict) -> dict:
    sector = contract.get("renormalizable_self_sector", {})
    checks = {
        "quadratic_count_sourced": sector.get("quadratic_invariant_count") == 1,
        "cubic_count_sourced": sector.get("cubic_invariant_count") == 1,
        "quartic_count_sourced": sector.get("quartic_invariant_count") == 4,
        "primary_sources_present": len(contract.get("primary_sources", [])) >= 2,
        "full_action_stays_open": contract.get("full_action_gate") == "NOT_COMPLETE",
        "mixed_invariants_stay_open": len(contract.get("still_unenumerated", [])) >= 4,
        "no_retuning": contract.get("no_retuning") is True,
        "publication_fail_closed": contract.get("publication_readiness") == "REVIEW_FAIL_CLOSED",
    }
    execution_pass = all(checks.values())
    return {
        "schema": "FTOE-SCALAR-ACTION-210-SELF-RESULT-v1.0",
        "checks": checks,
        "execution_pass": execution_pass,
        "scientific_verdict": (
            "PARTIAL_ACTION_210_SELF_SECTOR_SOURCE_ENUMERATED"
            if execution_pass
            else "SOURCE_OR_CONTRACT_INCOMPLETE"
        ),
        "scientific_pass": False,
        "full_action_complete": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.contract.read_text(encoding="utf-8")))
    output = json.dumps(result, indent=2, sort_keys=True)
    print(output)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output + "\n", encoding="utf-8")
    raise SystemExit(0 if result["execution_pass"] else 1)


if __name__ == "__main__":
    main()
