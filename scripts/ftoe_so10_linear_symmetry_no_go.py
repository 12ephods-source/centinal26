"""General no-go certificate for linear internal-symmetry protection of a scalar norm portal.

Let I and Phi transform in finite-dimensional unitary representations of any
ordinary internal symmetry G (continuous or discrete):

    I -> U_I(g) I,   Phi -> U_Phi(g) Phi.

Unitarity gives I^dagger I -> I^dagger U_I^dagger U_I I = I^dagger I and
similarly Phi^dagger Phi is invariant. Therefore the renormalizable operator

    (I^dagger I)(Phi^dagger Phi)

is invariant under G whenever it is gauge/Lorentz allowed. An ordinary linear
internal symmetry cannot forbid this norm portal. Protecting a hierarchy against
it requires a qualitatively different mechanism (nonlinear shift/Goldstone
symmetry, collective breaking where no single coupling generates the mass,
spacetime/geometric sequestering, supersymmetric cancellations, etc.).

This gate is representation-independent but intentionally narrow: it does not
claim a no-go for nonlinear or collective protection.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LinearSymmetryNoGo:
    schema: str
    assumptions: list[str]
    invariants: list[str]
    portal: str
    proof: list[str]
    ordinary_linear_internal_symmetry_status: str
    phase_ZN_status: str
    nonlinear_shift_or_collective_status: str
    sequestered_or_supersymmetric_status: str
    scientific_status: str


def certificate() -> LinearSymmetryNoGo:
    return LinearSymmetryNoGo(
        schema="FTOE-SO10-LINEAR-SYMMETRY-NOGO-v1",
        assumptions=[
            "I and every GUT scalar Phi transform linearly in finite-dimensional unitary representations of an ordinary internal symmetry G.",
            "The scalar kinetic terms use the standard positive Hermitian norm.",
            "The gauge/Lorentz quantum numbers allow the norm portal; I^dagger I and Phi^dagger Phi are singlets.",
        ],
        invariants=["I^dagger I", "Phi^dagger Phi"],
        portal="(I^dagger I)(Phi^dagger Phi)",
        proof=[
            "For any g in G, I -> U_I(g) I with U_I^dagger U_I = 1, hence I^dagger I is invariant.",
            "For any g in G, Phi -> U_Phi(g) Phi with U_Phi^dagger U_Phi = 1, hence Phi^dagger Phi is invariant.",
            "The product of two G-invariants is G-invariant, so the renormalizable norm portal cannot be forbidden by G.",
        ],
        ordinary_linear_internal_symmetry_status="FAIL",
        phase_ZN_status="FAIL",
        nonlinear_shift_or_collective_status="REVIEW",
        sequestered_or_supersymmetric_status="REVIEW",
        scientific_status="REVIEW",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = certificate()
    text = json.dumps(asdict(result), indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
