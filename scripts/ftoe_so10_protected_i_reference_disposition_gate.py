"""Fail-closed disposition for the direct Littlest-Higgs protected-I realization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_PARENT_GATE = "FAIL_DIRECT_IDENTIFICATION_HIGGS_ROLE_CONFLICT"
EXPECTED_DISPOSITION = "KILLED_FOR_DIRECT_IDENTIFICATION"


def evaluate(contract: dict) -> dict:
    checks = {
        "parent_gate_is_failed": contract.get("parent_gate") == EXPECTED_PARENT_GATE,
        "scientific_status_is_fail": contract.get("scientific_status") == "FAIL",
        "direct_identification_is_killed": contract.get("disposition") == EXPECTED_DISPOSITION,
        "no_retuning": contract.get("no_retuning") is True,
        "publication_remains_fail_closed": contract.get("publication_readiness") == "REVIEW_FAIL_CLOSED",
    }
    passed = all(checks.values())
    return {
        "schema": "FTOE-PROTECTED-I-REFERENCE-DISPOSITION-RESULT-v0.9",
        "checks": checks,
        "execution_pass": passed,
        "scientific_verdict": EXPECTED_DISPOSITION if passed else "DISPOSITION_CONTRACT_INVALID",
        "scientific_pass": False,
        "scope_limit": contract.get("scope_limit"),
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
