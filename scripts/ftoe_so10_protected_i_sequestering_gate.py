"""Fail-closed matching/sequestering gate for the lower-scale protected-I candidate.

This gate does not prove a UV completion. It asks a narrower question: is the
reference naturalness ceiling for the proposed protected-I sector parametrically
below the frozen G422->SM matching scale, so that the sector may consistently
emerge only after SO(10)/G422 breaking? If yes, an elementary SO(10) embedding is
not kinematically required. The dangerous high-scale portal is still a separate
matching problem and remains fail-closed until an explicit symmetry/sequestering
proof is supplied.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

MU_I_GEV = 9.54e3
ALPHA_REFERENCE = 0.032067325570772874
COEFFICIENT_C_REFERENCE = 1.0
M_I_G422_TO_SM_GEV = 7.0374912e9


def break_even_scale(mu_i: float = MU_I_GEV, alpha: float = ALPHA_REFERENCE, coefficient: float = COEFFICIENT_C_REFERENCE) -> float:
    if mu_i <= 0 or alpha <= 0 or coefficient <= 0:
        raise ValueError("mu_i, alpha, and coefficient must be positive")
    return mu_i / math.sqrt(coefficient * alpha / (4.0 * math.pi))


def calculate() -> dict:
    f_max = break_even_scale()
    ratio = f_max / M_I_G422_TO_SM_GEV
    decades = math.log10(M_I_G422_TO_SM_GEV / f_max)
    below_mi = f_max < M_I_G422_TO_SM_GEV
    return {
        "schema": "FTOE-PROTECTED-I-SEQUESTERING-GATE-v0.1",
        "scientific_status": "REVIEW",
        "inputs": {
            "mu_I_GeV": MU_I_GEV,
            "alpha_reference": ALPHA_REFERENCE,
            "coefficient_C_reference": COEFFICIENT_C_REFERENCE,
            "M_I_G422_to_SM_GeV": M_I_G422_TO_SM_GEV,
        },
        "derived": {
            "reference_f_max_GeV": f_max,
            "f_max_over_M_I": ratio,
            "separation_decades": decades,
        },
        "gates": {
            "protected_sector_can_emerge_below_M_I": "PASS" if below_mi else "FAIL",
            "elementary_SO10_irrep_embedding_required_by_scale": "NO" if below_mi else "UNRESOLVED",
            "SO10_to_protected_sector_portal_matching_derived": "FAIL",
            "O_MU2_mass_backreaction_excluded": "FAIL",
            "symmetry_or_sequestering_mechanism_frozen": "FAIL",
        },
        "interpretation": (
            "The candidate scale is parametrically below G422->SM breaking, so the protected-I sector may be treated as a low-energy emergent sector rather than an elementary SO(10) irrep. This removes the immediate representation-embedding requirement but does not remove high-scale threshold/portal matching."
            if below_mi
            else "The reference naturalness ceiling is not below the G422->SM scale; a low-energy-only emergence interpretation is not supported by this bound."
        ),
        "hard_falsifier": (
            "FAIL the candidate if integrating out the GUT/G422 sector generates an SO(5)-breaking relevant operator whose induced contribution to m_I^2 exceeds mu_I^2 without symmetry-enforced cancellation or sequestering."
        ),
        "next_required_derivation": (
            "Construct the leading operators connecting GUT/G422 scalar invariants to the SO(5)/SO(4) sector at M_I, classify them by SO(5)-breaking spurion order, and bound the induced pNGB mass after matching."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
