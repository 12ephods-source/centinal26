"""Reference bound for a lower-scale single-spurion pNGB protection branch.

This gate advances the active radiative-naturalness falsification without
constructing a new symmetry or representation.  It uses the same declared
one-loop scaling as ftoe_so10_radiative_protection_gate.py,

    delta m^2 = C * alpha/(4*pi) * f^2,

and solves it algebraically for the largest protection scale f compatible with
a target mass mu_I at a declared coefficient C.

The result is a necessary reference constraint only after C and the relevant
gauge coupling are frozen.  C=1 and alpha=alpha_U are retained solely as the
existing branch's preregistered reference convention; they are not promoted to
a representation-specific calculation.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LowScaleProtectionBound:
    schema: str
    mu_I_GeV: float
    alpha_reference: float
    coefficient_C: float
    spurion_per_C: float
    break_even_f_GeV: float
    break_even_f_TeV: float
    frozen_MU_GeV: float
    max_C_at_frozen_MU: float
    required_C_suppression_orders_at_frozen_MU: float
    reference_branch_status: str
    lower_scale_branch_status: str
    scientific_status: str
    assumptions: list[str]
    falsifier: str


def spurion_per_coefficient(alpha: float) -> float:
    if alpha <= 0.0:
        raise ValueError("alpha must be positive")
    return alpha / (4.0 * math.pi)


def break_even_scale(mu_i: float, alpha: float, coefficient: float = 1.0) -> float:
    if mu_i <= 0.0 or coefficient <= 0.0:
        raise ValueError("mu_I and coefficient must be positive")
    return mu_i / math.sqrt(coefficient * spurion_per_coefficient(alpha))


def max_coefficient(mu_i: float, f_scale: float, alpha: float) -> float:
    if mu_i <= 0.0 or f_scale <= 0.0:
        raise ValueError("mu_I and f_scale must be positive")
    return (mu_i / f_scale) ** 2 / spurion_per_coefficient(alpha)


def calculate(
    mu_i: float = 9.54e3,
    alpha: float = 0.032067325570772874,
    coefficient: float = 1.0,
    frozen_mu: float = 2.04990990688745e16,
) -> LowScaleProtectionBound:
    f_break = break_even_scale(mu_i, alpha, coefficient)
    c_at_mu = max_coefficient(mu_i, frozen_mu, alpha)
    orders = -math.log10(c_at_mu)
    return LowScaleProtectionBound(
        schema="FTOE-SO10-LOW-SCALE-PROTECTION-BOUND-v1",
        mu_I_GeV=mu_i,
        alpha_reference=alpha,
        coefficient_C=coefficient,
        spurion_per_C=spurion_per_coefficient(alpha),
        break_even_f_GeV=f_break,
        break_even_f_TeV=f_break / 1.0e3,
        frozen_MU_GeV=frozen_mu,
        max_C_at_frozen_MU=c_at_mu,
        required_C_suppression_orders_at_frozen_MU=orders,
        reference_branch_status="FAIL_ABOVE_BREAK_EVEN" if frozen_mu > f_break else "PASS_REFERENCE_BOUND",
        lower_scale_branch_status="REVIEW_REQUIRES_EXPLICIT_MECHANISM_AND_DERIVED_C",
        scientific_status="REVIEW",
        assumptions=[
            "Uses delta m^2 = C*alpha/(4*pi)*f^2, matching the existing radiative-protection gate convention.",
            "C=1 is a reference coefficient, not a derived SO(10) or pNGB group-theory coefficient.",
            "alpha_reference is held fixed at the already frozen branch reference value; a concrete lower-scale mechanism must run and derive its own coupling/coefficient.",
            "Collective cancellations, sequestering, supersymmetry, or additional spurion powers are not represented by this single-spurion bound.",
        ],
        falsifier=(
            "For a future explicit single-spurion mechanism with frozen positive C and alpha, "
            "the branch fails this naturalness condition if its protection scale exceeds "
            "mu_I/sqrt(C*alpha/(4*pi))."
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--muI", type=float, default=9.54e3)
    parser.add_argument("--alpha", type=float, default=0.032067325570772874)
    parser.add_argument("--C", type=float, default=1.0)
    parser.add_argument("--MU", type=float, default=2.04990990688745e16)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate(args.muI, args.alpha, args.C, args.MU)
    text = json.dumps(asdict(result), indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
