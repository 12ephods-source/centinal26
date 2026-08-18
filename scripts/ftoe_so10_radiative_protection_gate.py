"""Fail-closed radiative-protection gate for the informational scalar.

This is a scaling/naturalness test, not a representation-specific mass calculation.
If a putative pNGB at decay constant f is charged under a gauged subgroup that
explicitly breaks its protecting global symmetry, a generic one-loop contribution
has the parametric size

    delta m^2 ~ C * g^2/(16*pi^2) * f^2,

with unknown representation-dependent C.  We therefore report C=1 only as a
reference scale and ask how many comparable loop/spurion suppressions would be
needed to reach the target mu_I.  A specific model must still derive its exact C,
collective-breaking structure, and counterterm/radiative stability.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ProtectionResult:
    schema: str
    f_GeV: float
    mu_I_GeV: float
    alpha_U: float
    g_U: float
    target_mass_squared_ratio: float
    one_loop_gauge_spurion: float
    reference_one_loop_mass_GeV: float
    reference_one_loop_mass_over_mu_I: float
    minimum_equal_spurion_loop_order: int
    gates: dict[str, str]
    single_spurion_GUT_scale_pNGB_status: str
    collective_or_sequestered_branch_status: str
    scientific_status: str
    notes: list[str]


def minimum_loop_order(spurion: float, target: float) -> int:
    if not (0.0 < spurion < 1.0 and 0.0 < target < 1.0):
        raise ValueError("spurion and target must lie strictly between zero and one")
    order = 1
    while spurion**order > target:
        order += 1
        if order > 1000:
            raise RuntimeError("loop-order search did not converge")
    return order


def calculate(f_gev: float, mu_i_gev: float, alpha_u: float) -> ProtectionResult:
    if not (f_gev > 0.0 and mu_i_gev > 0.0 and alpha_u > 0.0):
        raise ValueError("all inputs must be positive")
    if mu_i_gev >= f_gev:
        raise ValueError("mu_I must lie below the protection scale f")

    g_u = math.sqrt(4.0 * math.pi * alpha_u)
    target = (mu_i_gev / f_gev) ** 2
    spurion = g_u**2 / (16.0 * math.pi**2)
    m1 = f_gev * math.sqrt(spurion)
    loops = minimum_loop_order(spurion, target)

    gates = {
        "target_hierarchy_quantified": "PASS",
        "generic_one_loop_gauge_lift_below_target": "FAIL" if spurion > target else "PASS",
        "single_spurion_GUT_scale_pNGB_natural": "FAIL" if spurion > target else "PASS",
        "explicit_collective_breaking_structure": "NOT_TESTED",
        "exact_shift_symmetry_compatible_with_required_gauge_couplings": "NOT_TESTED",
        "representation_specific_one_loop_coefficient": "NOT_TESTED",
        "all_lower_order_symmetry_breaking_spurions_excluded": "NOT_TESTED",
        "radiative_stability_to_required_order": "NOT_TESTED",
    }

    return ProtectionResult(
        schema="FTOE-SO10-RADIATIVE-PROTECTION-GATE-v0.1",
        f_GeV=f_gev,
        mu_I_GeV=mu_i_gev,
        alpha_U=alpha_u,
        g_U=g_u,
        target_mass_squared_ratio=target,
        one_loop_gauge_spurion=spurion,
        reference_one_loop_mass_GeV=m1,
        reference_one_loop_mass_over_mu_I=m1 / mu_i_gev,
        minimum_equal_spurion_loop_order=loops,
        gates=gates,
        single_spurion_GUT_scale_pNGB_status="FAIL" if spurion > target else "PASS",
        collective_or_sequestered_branch_status="REVIEW",
        scientific_status="REVIEW",
        notes=[
            "C=1 is a reference scaling only; the exact pNGB mass coefficient is representation and potential dependent.",
            "The FAIL is limited to a GUT-scale pNGB whose protection is broken by a single ordinary gauge spurion at one loop.",
            "Collective breaking, exact sequestering, supersymmetric protection, or a lower symmetry-breaking scale are distinct branches and remain NOT_TESTED/REVIEW.",
            "A viable branch must derive the protecting symmetry and show that every lower-order explicit-breaking invariant is absent, not merely small after fitting.",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--f", type=float, default=2.04990990688745e16)
    parser.add_argument("--muI", type=float, default=9.54e3)
    parser.add_argument("--alphaU", type=float, default=0.032067325570772874)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate(args.f, args.muI, args.alphaU)
    text = json.dumps(asdict(result), indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
