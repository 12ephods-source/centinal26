"""Fail-closed structural gate for the versioned protected-I Littlest-Higgs candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_OPEN = (
    "identify_I_with_reference_pNGB_without_higgs_role_conflict",
    "so10_compatible_embedding_or_sequestering",
    "portal_suppression",
    "representation_specific_radiative_mass",
    "precision_and_partner_constraints",
)


def evaluate(c: dict) -> dict:
    m = c.get("mechanism", {})
    scope = c.get("frozen_scope", {})
    nxt = c.get("mandatory_next_gates", {})
    structural = {
        "explicit_coset": m.get("coset") == "SU(5)/SO(5)",
        "collective_gauge_structure": bool(m.get("collective_gauge_structure")),
        "pngb_doublet": m.get("pNGB_doublet") is True,
        "partner_cancellation_reference": (
            m.get("same_statistics_partners") is True
            and m.get("one_loop_quadratic_cancellation_reference") is True
        ),
        "primary_reference_frozen": m.get("reference_source") == "arXiv:hep-ph/0206021",
        "hard_failure_versioning": (
            scope.get("introduces_new_symmetry_after_hard_parent_failure") is True
        ),
        "no_resurrection": scope.get("does_not_resurrect_killed_so5_so4_candidate") is True,
        "all_compatibility_gates_open": all(nxt.get(k) == "NOT_DERIVED" for k in REQUIRED_OPEN),
    }
    ok = all(structural.values())
    return {
        "schema": "FTOE-PROTECTED-I-LITTLEST-HIGGS-ADJUDICATION-v0.7",
        "checks": structural,
        "gate": (
            "REFERENCE_COLLECTIVE_MECHANISM_STRUCTURALLY_SPECIFIED"
            if ok
            else "FAIL_REFERENCE_MECHANISM_CONTRACT"
        ),
        "scientific_status": "REVIEW",
        "claim": (
            "A literature-backed collective pNGB mechanism is now explicit enough to test, "
            "but FToE compatibility is not derived."
        ),
        "scope_limit": (
            "This is not an SO(10) embedding, mu_I derivation, portal proof, precision fit, "
            "or publication PASS."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.candidate.read_text(encoding="utf-8")))
    serialized = json.dumps(result, indent=2, sort_keys=True)
    print(serialized)
    if args.json:
        args.json.write_text(serialized + "\n", encoding="utf-8")
    raise SystemExit(
        0 if result["gate"] == "REFERENCE_COLLECTIVE_MECHANISM_STRUCTURALLY_SPECIFIED" else 1
    )


if __name__ == "__main__":
    main()
