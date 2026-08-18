#!/usr/bin/env python3
"""Deterministic no-go for exact additive-shift protection of the frozen linear I doublet.

Scope
-----
The current FToE low-energy informational field is a linearly realized electroweak
scalar I ~ (1,2,+1/2).  Consider an exact constant additive shift

    I(x) -> I(x) + epsilon,

with nonzero constant epsilon in the same representation.  For an ordinary gauge
covariant derivative D_mu = partial_mu - i g_a A_mu^a T^a,

    D_mu(I + epsilon) = D_mu I - i g_a A_mu^a T^a epsilon.

Exact invariance of |D_mu I|^2 for arbitrary gauge fields therefore requires
T^a epsilon = 0 for every gauged generator with nonzero coupling.  For the frozen
I doublet this is impossible for any nonzero epsilon: already hypercharge
Y=+1/2 gives Y epsilon = epsilon/2 != 0.

This kills only the exact additive-shift symmetry of the existing linearly
realized charged doublet.  It does NOT exclude nonlinear pNGB realizations,
collective breaking with additional structure, geometric sequestering, SUSY
cancellations, or a lower protection scale.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExactShiftResult:
    schema: str
    representation: str
    hypercharge: float
    required_nonzero_gauge_coupling: bool
    nontrivial_constant_shift_exists: bool
    exact_additive_shift_status: str
    nonlinear_collective_or_sequestered_status: str
    scientific_status: str
    proof: list[str]
    limitations: list[str]


def nontrivial_constant_shift_exists(hypercharge: float, gauge_coupling_nonzero: bool) -> bool:
    """Return whether a nonzero constant shift can survive the gauged U(1) factor.

    For a field with charge Y and nonzero gauge coupling, exact invariance requires
    Y * epsilon = 0.  If Y != 0, only epsilon=0 is allowed.
    """
    if not gauge_coupling_nonzero:
        return True
    return hypercharge == 0.0


def calculate(hypercharge: float = 0.5, gauge_coupling_nonzero: bool = True) -> ExactShiftResult:
    survives = nontrivial_constant_shift_exists(hypercharge, gauge_coupling_nonzero)
    status = "REVIEW" if survives else "FAIL"
    return ExactShiftResult(
        schema="FTOE-SO10-EXACT-SHIFT-NO-GO-v1",
        representation="I ~ (1,2,+1/2)",
        hypercharge=hypercharge,
        required_nonzero_gauge_coupling=gauge_coupling_nonzero,
        nontrivial_constant_shift_exists=survives,
        exact_additive_shift_status=status,
        nonlinear_collective_or_sequestered_status="REVIEW",
        scientific_status="REVIEW",
        proof=[
            "For constant epsilon, partial_mu epsilon = 0.",
            "Gauge covariance gives D_mu(I+epsilon)=D_mu I-i g' B_mu Y epsilon (plus non-Abelian terms).",
            "Exact invariance for arbitrary B_mu requires g' Y epsilon=0.",
            "The frozen informational doublet has Y=+1/2 and requires nonzero electroweak gauge coupling, hence epsilon=0.",
            "Therefore no nontrivial exact additive shift symmetry exists for the current linearly realized charged I field.",
        ],
        limitations=[
            "This is not a no-go theorem for nonlinear Goldstone realizations.",
            "It does not exclude collective breaking, sequestering, supersymmetric cancellation, or lower-scale protection.",
            "Any surviving collective/nonlinear branch must be explicitly versioned and must derive all additional structure rather than assuming it.",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hypercharge", type=float, default=0.5)
    parser.add_argument("--gauge-coupling-zero", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate(args.hypercharge, not args.gauge_coupling_zero)
    text = json.dumps(asdict(result), indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
