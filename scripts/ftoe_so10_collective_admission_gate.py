"""Fail-closed admission gate for collective/sequestered informational protection.

This gate does not invent a protected sector. It asks a narrower question:
can the currently frozen SO(10)/G422 branch claim that a collective or sequestered
mechanism has actually been specified well enough to close radiative naturalness?

Collective symmetry breaking requires the protecting symmetry to survive when
individual explicit-breaking couplings are switched off; the Higgs/pNGB mass is
then generated only by the interplay of multiple couplings. See hep-ph/0206021
and hep-ph/0502182 for explicit constructions/review. A sequestered mechanism
must likewise specify the locality/geometric rule that forbids the dangerous
local operator, not merely set its coefficient small.

The current branch remains fail-closed if its protected_I_sector is absent or if
no explicit nonlinear/collective/sequestered structure and portal-suppression
proof are frozen in the UV contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "physics" / "ftoe" / "uv_model_contract.json"


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(contract: dict) -> dict:
    reps = contract.get("required_so10_representations", {})
    protected = reps.get("protected_I_sector", {})
    provenance = contract.get("scalar_potential_provenance", {})
    invariants = contract.get("hard_invariants", [])

    status = str(protected.get("status", "MISSING"))
    mechanism = protected.get("mechanism")
    symmetry_structure = protected.get("symmetry_structure")
    collective_couplings = protected.get("collective_breaking_couplings", [])
    portal_proof = protected.get("portal_suppression_proof")
    radiative_proof = protected.get("radiative_stability_proof")
    sequestering_rule = protected.get("sequestering_rule")

    constructed = status in {"CONSTRUCTED", "FROZEN", "VERIFIED"}
    explicit_mechanism = bool(mechanism and (symmetry_structure or sequestering_rule))
    collective_structure = bool(
        isinstance(collective_couplings, list)
        and len(collective_couplings) >= 2
        and symmetry_structure
    )
    sequestered_structure = bool(sequestering_rule)
    protection_structure = collective_structure or sequestered_structure
    portal_closed = bool(portal_proof)
    radiative_closed = bool(radiative_proof)
    contract_requires_portal_suppression = any(
        "protected informational sector must remove or symmetry-suppress" in str(item).lower()
        for item in invariants
    )
    provenance_still_open = "OPEN" in str(provenance.get("protected_I_extension", ""))

    admission_pass = all(
        (
            constructed,
            explicit_mechanism,
            protection_structure,
            portal_closed,
            radiative_closed,
            contract_requires_portal_suppression,
            not provenance_still_open,
        )
    )

    gates = {
        "protected_sector_constructed": "PASS" if constructed else "FAIL",
        "explicit_nonlinear_or_sequestered_mechanism": "PASS" if explicit_mechanism else "FAIL",
        "collective_or_sequestered_structure_frozen": "PASS" if protection_structure else "FAIL",
        "renormalizable_portal_suppression_proved": "PASS" if portal_closed else "FAIL",
        "radiative_stability_proved": "PASS" if radiative_closed else "FAIL",
        "uv_contract_requires_portal_suppression": "PASS" if contract_requires_portal_suppression else "FAIL",
        "protected_I_extension_closed_in_provenance": "PASS" if not provenance_still_open else "FAIL",
    }

    return {
        "schema": "FTOE-COLLECTIVE-PROTECTION-ADMISSION-v1",
        "active_publication_gate": "radiative_naturalness",
        "current_contract_status": contract.get("status", "UNKNOWN"),
        "protected_I_sector_status": status,
        "collective_protection_admission": "PASS" if admission_pass else "FAIL_CURRENT_FROZEN_BRANCH",
        "scientific_status": "REVIEW" if not admission_pass else "REVIEW_PENDING_INDEPENDENT_REPRODUCTION",
        "gates": gates,
        "primary_source_criterion": {
            "hep-ph/0206021": "explicit little-Higgs construction with nonlinear pNGB structure and partner states",
            "hep-ph/0502182": "collective breaking requires multiple couplings whose interplay breaks all protecting symmetries",
        },
        "derived_statement": (
            "The current frozen branch cannot claim collective/sequestered protection because the protected_I_sector is not constructed and no explicit protecting structure, portal-suppression proof, or radiative-stability proof is frozen. Any surviving mechanism therefore requires an explicitly versioned branch revision; this result is not a no-go theorem against all possible collective or sequestered theories."
            if not admission_pass
            else "The mechanism satisfies the structural admission contract but still requires independent scientific reproduction."
        ),
        "no_retuning_statement": "No downstream mass, threshold, RGE, inflation, dark-sector, or proton-decay parameter is changed by this gate.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = evaluate(load_contract(args.contract))
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    # FAIL_CURRENT_FROZEN_BRANCH is the expected scientific result for the present
    # contract, not an execution failure. Machine execution succeeds if evaluated.


if __name__ == "__main__":
    main()
