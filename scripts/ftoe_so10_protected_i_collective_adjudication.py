"""Fail-closed collective-protection adjudication for the protected-I candidate.

This gate does not claim a no-go theorem against all collective or sequestered
models. It asks whether the current versioned SO(5)/SO(4) candidate contains the
minimum explicit structure required to claim collective radiative protection.

Primary criterion: collective symmetry breaking requires two or more explicit-
breaking couplings whose individual removal restores enough symmetry to protect
the pNGB mass (arXiv:hep-ph/0502182). Concrete little-Higgs constructions also
contain partner states/interactions responsible for one-loop cancellation
(arXiv:hep-ph/0206021).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "physics" / "ftoe" / "protected_I_so5_so4_candidate.json"


def evaluate(candidate: dict) -> dict:
    couplings = candidate.get("collective_breaking_couplings", [])
    restoration = candidate.get("symmetry_restoration_tests", [])
    partners = candidate.get("partner_states", [])
    cancellation = candidate.get("one_loop_cancellation_proof")
    bound = candidate.get("radiative_mass_bound")

    checks = {
        "at_least_two_collective_couplings": isinstance(couplings, list) and len(couplings) >= 2,
        "symmetry_restoration_when_each_coupling_off": (
            isinstance(restoration, list)
            and len(restoration) >= 2
            and all(bool(item) for item in restoration)
        ),
        "partner_states_enumerated": isinstance(partners, list) and len(partners) > 0,
        "one_loop_cancellation_proved": bool(cancellation),
        "radiative_mass_bound_derived": bool(bound),
    }
    passed = all(checks.values())

    return {
        "schema": "FTOE-PROTECTED-I-COLLECTIVE-ADJUDICATION-v0.3",
        "candidate_schema": candidate.get("schema", "UNKNOWN"),
        "mechanism_class": candidate.get("mechanism_class", "UNKNOWN"),
        "checks": checks,
        "gate": (
            "COLLECTIVE_PROTECTION_STRUCTURALLY_SPECIFIED"
            if passed
            else "FAIL_CURRENT_MINIMAL_CANDIDATE"
        ),
        "scientific_status": (
            "REVIEW_PENDING_RADIATIVE_CALCULATION"
            if passed
            else "FAIL_MINIMAL_SO5_SO4_COLLECTIVE_PROTECTION"
        ),
        "derived_statement": (
            "The current candidate specifies no qualifying collective-breaking coupling set, "
            "symmetry-restoration tests, partner spectrum, one-loop cancellation proof, or "
            "derived radiative mass bound. Therefore the minimal SO(5)/SO(4) candidate cannot "
            "satisfy the collective-protection admission gate as written."
            if not passed
            else "The structural collective-protection contract is populated; numerical radiative "
            "stability still requires independent calculation."
        ),
        "scope_limit": (
            "This rejects only the current minimal candidate. It is not a no-go theorem against "
            "separately versioned little-Higgs, collective, sequestered, or other protected extensions."
        ),
        "primary_sources": ["arXiv:hep-ph/0502182", "arXiv:hep-ph/0206021"],
        "no_retuning": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    result = evaluate(candidate)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
