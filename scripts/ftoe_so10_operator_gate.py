#!/usr/bin/env python3
"""FToE L1 operator/symmetry closure gate.

This module does not pretend to enumerate SO(10) tensor contractions from first
principles.  It certifies the selection-rule statements that *can* be proved
from charges alone and fails closed on the genuinely group-theoretic pieces.

Scientific purpose:
  1. prove that an ordinary phase Z_N cannot forbid R^\dagger R;
  2. prove the same-Higgs Yukawa-compatible Z_N no-go for 10*126*210;
  3. search cyclic selectors for a spurion tower B_3 S^k whose first allowed
     member is at a requested operator dimension;
  4. scan the Planck-suppression power implied by the independently computed
     unification scale M_U;
  5. emit PASS/REVIEW/FAIL gates without upgrading uncomputed Clebsch factors.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

MP = 1.22089e19
MU_I = 9.54e3


def neutral_bilinear_charge(q: int, n: int) -> int:
    """Charge of R^dagger R under an ordinary phase Z_N."""
    if n < 2:
        raise ValueError("N must be >= 2")
    return (-q + q) % n


def same_higgs_no_go(n: int, q16: int) -> Dict[str, int | bool]:
    """Charge-algebra no-go with conventional shared Yukawa Higgs fields.

    Assumptions, modulo N:
      16_F 16_F 10_H allowed          -> h = -2 x
      16_F 16_F bar126_H allowed      -> dbar = -2 x
      126_H bar126_H allowed          -> d = 2 x
      210_H^2 and 210_H^3 allowed     -> p = 0

    Then q(10_H 126_H 210_H)=h+d+p=0 for every N and x.
    """
    if n < 2:
        raise ValueError("N must be >= 2")
    x = q16 % n
    h = (-2*x) % n
    dbar = (-2*x) % n
    d = (2*x) % n
    # 2p=3p=0 mod N implies p=0 since gcd(2,3)=1.
    p = 0
    cubic = (h + d + p) % n
    return {
        "N": n,
        "q16": x,
        "q10H": h,
        "q126H": d,
        "qbar126H": dbar,
        "q210H": p,
        "q_10_126_210": cubic,
        "cubic_forced_allowed": cubic == 0,
    }


def first_allowed_spurion_power(n: int, q_b: int, q_s: int, max_k: int = 64) -> Optional[int]:
    if n < 2:
        raise ValueError("N must be >= 2")
    for k in range(max_k + 1):
        if (q_b + k*q_s) % n == 0:
            return k
    return None


def selector_search(target_dimension: int, n_max: int = 64) -> List[Dict[str, int]]:
    """Find Z_N selectors for B_3 S^k with first allowed dimension target_dimension.

    B_3 has dimension 3 and S has dimension 1, so k=target_dimension-3.
    We require no earlier k>=0 member of this *specific spurion tower* to be
    neutral.  This is not an exhaustive SO(10)-invariant enumeration.
    """
    target_k = target_dimension - 3
    if target_k < 0:
        raise ValueError("target dimension must be >= 3")
    rows = []
    for n in range(2, n_max + 1):
        for qb in range(1, n):
            for qs in range(1, n):
                first = first_allowed_spurion_power(n, qb, qs, max_k=max(target_k, n + 2))
                if first == target_k:
                    rows.append({"N": n, "q_B3": qb, "q_S": qs, "first_allowed_k": first, "dimension": first + 3})
    rows.sort(key=lambda r: (r["N"], r["q_B3"], r["q_S"]))
    return rows


def hierarchy_scan(m_u: float, n_min: int = 1, n_max: int = 12) -> List[Dict[str, float | int]]:
    if not (0.0 < m_u < MP):
        raise ValueError("M_U must lie between 0 and M_P")
    target = (MU_I/m_u)**2
    ratio = m_u/MP
    rows = []
    for power in range(n_min, n_max + 1):
        coeff = target/(ratio**power)
        rows.append({"power": power, "operator_dimension_if_mass_bilinear_plus_insertions": power + 4,
                     "coefficient_times_Ceff": coeff, "log10_abs_coefficient": math.log10(abs(coeff))})
    return rows


@dataclass
class GateResult:
    schema: str
    M_U_GeV: float
    target_mu_I_GeV: float
    preferred_power: int
    preferred_operator_dimension: int
    preferred_coefficient_times_Ceff: float
    smallest_selector: Dict[str, int]
    gates: Dict[str, str]
    scientific_status: str
    notes: List[str]


def calculate(m_u: float) -> GateResult:
    scan = hierarchy_scan(m_u)
    best = min(scan, key=lambda r: abs(r["log10_abs_coefficient"]))
    target_dim = int(best["operator_dimension_if_mass_bilinear_plus_insertions"])
    selectors = selector_search(target_dim)
    smallest = selectors[0] if selectors else {}

    # Algebraic checks over several moduli make the universal no-go executable.
    no_go_ok = all(same_higgs_no_go(n, x)["cubic_forced_allowed"] for n in range(2, 33) for x in range(n))
    bilinear_ok = all(neutral_bilinear_charge(q, n) == 0 for n in range(2, 33) for q in range(n))

    coeff = float(best["coefficient_times_Ceff"])
    hierarchy_natural = 0.1 <= abs(coeff) <= 10.0
    gates = {
        "ordinary_phase_symmetry_cannot_forbid_RdaggerR": "PASS" if bilinear_ok else "FAIL",
        "same_higgs_Yukawa_compatible_ZN_no_go": "PASS" if no_go_ok else "FAIL",
        "preferred_suppression_has_order_one_effective_coefficient": "PASS" if hierarchy_natural else "REVIEW",
        "cyclic_selector_exists_for_specific_B3_Sk_tower": "PASS" if smallest else "FAIL",
        "separate_informational_multiplets_required_by_no_go": "DERIVED",
        "explicit_SO10_tensor_contraction_at_preferred_dimension": "NOT_TESTED",
        "actual_Clebsch_factor_Ceff": "NOT_TESTED",
        "exhaustive_lower_dimension_SO10_invariant_exclusion": "NOT_TESTED",
        "protecting_continuous_or_accidental_symmetry_realized_in_full_potential": "NOT_TESTED",
    }
    scientific_status = "FAIL" if "FAIL" in gates.values() else "REVIEW"
    return GateResult(
        schema="FTOE-SO10-OPERATOR-GATE-v0.1",
        M_U_GeV=m_u,
        target_mu_I_GeV=MU_I,
        preferred_power=int(best["power"]),
        preferred_operator_dimension=target_dim,
        preferred_coefficient_times_Ceff=coeff,
        smallest_selector=smallest,
        gates=gates,
        scientific_status=scientific_status,
        notes=[
            "A Z_N phase symmetry cannot protect a scalar quadratic norm R^dagger R.",
            "With conventional shared 10_H/bar126_H Yukawas plus 126_H bar126_H and 210_H^2,210_H^3, the 10_H 126_H 210_H charge is forced neutral.",
            "The selector PASS applies only to the chosen B_3 S^k spurion tower; it is not an exhaustive tensor-invariant proof.",
            "The hierarchy coefficient is c*C_eff.  C_eff remains uncomputed until an explicit SO(10) contraction and pNGB eigenvector are fixed.",
        ],
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--MU", type=float, default=2.04990990688745e16, help="Unification scale in GeV")
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    result = calculate(args.MU)
    text = json.dumps(asdict(result), indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
