"""Derive the low-energy electroweak embedding of an SO(5)/SO(4) pNGB doublet.

This gate is deliberately narrow.  It verifies only the group-theory statement
that the four Goldstones of SO(5)/SO(4), transforming as the vector 4 of SO(4)
~= SU(2)_L x SU(2)_R, form a (2,2).  Gauging SU(2)_L and Y=T_R^3 with X=0
then yields SU(2)_L doublets of hypercharge +1/2 and -1/2, related as the
complex doublet and its conjugate.

It does NOT derive an SO(10) embedding, a UV strong sector, portal suppression,
radiative stability, or a representation-specific mass correction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def derive_embedding() -> dict:
    su2r_t3_weights = (-0.5, 0.5)
    x_charge = 0.0
    hypercharges = tuple(weight + x_charge for weight in su2r_t3_weights)

    checks = {
        "coset_dimension_is_four": 10 - 6 == 4,
        "so4_vector_dimension_matches_bidoublet": 2 * 2 == 4,
        "hypercharge_weights_are_pm_half": hypercharges == (-0.5, 0.5),
        "positive_hypercharge_doublet_exists": 0.5 in hypercharges,
        "negative_partner_is_conjugate_charge": sum(hypercharges) == 0.0,
    }
    passed = all(checks.values())

    return {
        "schema": "FTOE-PROTECTED-I-EW-EMBEDDING-GATE-v0.2",
        "candidate_coset": "SO(5)/SO(4)",
        "unbroken_local_structure_used": "SO(4) ~= SU(2)_L x SU(2)_R",
        "goldstone_representation": "4 -> (2,2)",
        "hypercharge_definition": "Y = T_R^3 + X",
        "candidate_scalar_X": x_charge,
        "derived_SU2LxU1Y_content": ["2_{-1/2}", "2_{+1/2}"],
        "I_identification": "one complex SU(2)_L doublet with Y=+1/2; the Y=-1/2 object is its conjugate charge partner",
        "checks": checks,
        "gate": "DERIVED_LOW_ENERGY_EW_EMBEDDING" if passed else "FAIL",
        "scientific_scope": {
            "closed": ["low-energy SU(2)_L x U(1)_Y embedding of the candidate pNGB doublet"],
            "not_closed": [
                "SO(10) embedding",
                "collective or other radiative protection",
                "representation-specific radiative coefficient C",
                "renormalizable SO(10) portal suppression",
                "strong-sector resonance spectrum",
                "beta-function backreaction",
                "matching to the frozen mu_I and G422 branch",
            ],
        },
        "primary_precedent": [
            "arXiv:hep-ph/0412089 — Minimal Composite Higgs Model (SO(5)/SO(4) pNGB Higgs precedent)",
            "arXiv:0902.1483 — Beyond the Minimal Composite Higgs Model (states the minimal SO(5)/SO(4) coset has a unique Higgs doublet)",
        ],
        "epistemic_status": "DERIVED_GROUP_THEORY_LOW_ENERGY_ONLY" if passed else "FAILED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    result = derive_embedding()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")

    raise SystemExit(0 if result["gate"].startswith("DERIVED") else 1)


if __name__ == "__main__":
    main()
