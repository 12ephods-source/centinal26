from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate(candidate: dict) -> dict:
    structure = candidate.get("source_supported_structure", {})
    roles = candidate.get("role_assignment_hypothesis", {})
    mandatory = candidate.get("mandatory_gates", {})

    checks = {
        "source_is_frozen": candidate.get("primary_source") == "arXiv:1105.5403",
        "two_pNGB_doublets_present": structure.get("two_light_pNGB_electroweak_doublets") is True,
        "distinguishing_symmetry_present": structure.get("discrete_symmetry_can_distinguish_doublets") is True,
        "inert_second_doublet_reference_present": structure.get("inert_second_doublet_realization_discussed") is True,
        "roles_are_separated": roles.get("doublet_1") == "SM_HIGGS_REFERENCE_ROLE" and roles.get("doublet_2") == "PROTECTED_I_CANDIDATE_ROLE",
        "fToe_specific_gates_remain_open": all(
            mandatory.get(key) == "NOT_DERIVED"
            for key in (
                "identify_second_doublet_with_I_quantum_numbers",
                "mu_I_13p5_TeV_mass_matching",
                "SO10_embedding_or_sequestering",
                "portal_suppression",
                "representation_specific_radiative_mass",
                "precision_and_partner_constraints",
            )
        ),
        "no_retuning": candidate.get("no_retuning") is True,
    }
    passed = all(checks.values())
    return {
        "schema": "FTOE-PROTECTED-I-SO6-ROLE-SEPARATION-ADJUDICATION-v1.4",
        "checks": checks,
        "gate": "ROLE_SEPARATED_REFERENCE_MECHANISM_STRUCTURALLY_SPECIFIED" if passed else "FAIL_REFERENCE_STRUCTURE_CONTRACT",
        "scientific_status": "REVIEW" if passed else "FAIL",
        "claim": "SO(6)/(SO(4)xSO(2)) supplies a literature-backed two-pNGB-doublet reference in which SM-Higgs and protected-I candidate roles need not be the same doublet.",
        "scope_limit": "Structural reference only; FToE quantum-number identification, mass matching, SO(10), portals, radiative stability, and precision constraints remain unproved.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.candidate.read_text(encoding="utf-8")))
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    raise SystemExit(0 if result["gate"] == "ROLE_SEPARATED_REFERENCE_MECHANISM_STRUCTURALLY_SPECIFIED" else 1)


if __name__ == "__main__":
    main()
