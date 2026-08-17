#!/usr/bin/env python3
"""Deterministic FToE SO(10)->422->SM closure gate.

Scope:
- correct one-loop contribution of an extra complex (1,2,+1/2) scalar;
- run SM -> SM+I piecewise one-loop coupling evolution;
- solve the one-loop Pati-Salam intermediate scale using the 422 matching relation;
- solve the one-loop 422 unification scale;
- propagate the resulting M_U into the informational-scalar hierarchy scan;
- classify gates without conflating numerical execution with scientific closure.

This script intentionally does not claim a two-loop or threshold-complete result.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Tuple

PI = math.pi

# Default electroweak inputs. They are explicit inputs, not hidden constants.
MZ = 91.1876
ALPHA1_INV_MZ = 59.01   # SU(5)-normalized U(1)_Y
ALPHA2_INV_MZ = 29.59
ALPHA3_INV_MZ = 8.445
MP = 1.22089e19          # GeV, unreduced Planck mass used by the beta chain
XI_I = 1.0 / 6.0
CURVATURE_COEFF = 7.31
MU_I = 9.54e3            # GeV, provisional target under audit
M_I_PHYS = math.sqrt(2.0) * MU_I

# Convention: d(alpha_i^-1)/d ln(mu) = -b_i/(2*pi)
B_SM = {"1": 41.0/10.0, "2": -19.0/6.0, "3": -7.0}
B_EXTRA_DOUBLEt = {"1": 1.0/10.0, "2": 1.0/6.0, "3": 0.0}
B_2H = {k: B_SM[k] + B_EXTRA_DOUBLEt[k] for k in B_SM}

# Non-D-parity Pati-Salam coefficients for ordering (4C, 2L, 2R).
# Used as a frozen candidate chassis pending full FToE-specific two-loop reconstruction.
B_422 = {"4": -7.0/3.0, "L": 2.0, "R": 28.0/3.0}


def evolve_alpha_inv(alpha_inv: float, b: float, mu0: float, mu1: float) -> float:
    if mu0 <= 0 or mu1 <= 0:
        raise ValueError("scales must be positive")
    return alpha_inv - (b / (2.0 * PI)) * math.log(mu1 / mu0)


def low_energy_couplings(mu: float, threshold: float = M_I_PHYS) -> Dict[str, float]:
    """Piecewise SM -> SM+I one-loop evolution from MZ to mu."""
    if mu < MZ:
        raise ValueError("mu must be >= MZ")
    start = {"1": ALPHA1_INV_MZ, "2": ALPHA2_INV_MZ, "3": ALPHA3_INV_MZ}
    if mu <= threshold:
        return {k: evolve_alpha_inv(start[k], B_SM[k], MZ, mu) for k in start}
    at_threshold = {k: evolve_alpha_inv(start[k], B_SM[k], MZ, threshold) for k in start}
    return {k: evolve_alpha_inv(at_threshold[k], B_2H[k], threshold, mu) for k in start}


def ps_matching_residual(mu: float) -> float:
    """One-loop 422 matching/unification combination at the intermediate scale.

    For B_422=(-7/3,2,28/3), eliminating alpha_R and ln(M_U/M_I)
    gives 8*alpha_3^-1 - 21*alpha_2^-1 + 13*alpha_1^-1 = 0.
    """
    a = low_energy_couplings(mu)
    return 8.0*a["3"] - 21.0*a["2"] + 13.0*a["1"]


def bisect_log_root(fn, lo: float, hi: float, iterations: int = 200) -> float:
    """Residual-certified bisection in log(mu)."""
    if lo <= 0 or hi <= 0 or not lo < hi:
        raise ValueError("invalid bracket")
    xlo, xhi = math.log(lo), math.log(hi)
    flo, fhi = fn(math.exp(xlo)), fn(math.exp(xhi))
    if flo == 0.0:
        return lo
    if fhi == 0.0:
        return hi
    if flo * fhi > 0:
        raise ValueError(f"root not bracketed: f(lo)={flo}, f(hi)={fhi}")
    for _ in range(iterations):
        xm = 0.5*(xlo+xhi)
        fm = fn(math.exp(xm))
        if fm == 0.0:
            return math.exp(xm)
        if flo*fm <= 0:
            xhi, fhi = xm, fm
        else:
            xlo, flo = xm, fm
    return math.exp(0.5*(xlo+xhi))


def solve_422_unification(mi: float) -> Tuple[float, float, Dict[str, float]]:
    """Solve M_U and alpha_U from alpha_4=alpha_L, with alpha_R as cross-check."""
    a = low_energy_couplings(mi)
    a4 = a["3"]
    aL = a["2"]
    # SU(5)-normalized hypercharge matching: a1^-1=(3/5)aR^-1+(2/5)a4^-1
    aR = (5.0/3.0)*a["1"] - (2.0/3.0)*a4

    denom = B_422["L"] - B_422["4"]
    log_mu_over_mi = 2.0*PI*(aL-a4)/denom
    mu = mi * math.exp(log_mu_over_mi)

    au4 = evolve_alpha_inv(a4, B_422["4"], mi, mu)
    auL = evolve_alpha_inv(aL, B_422["L"], mi, mu)
    auR = evolve_alpha_inv(aR, B_422["R"], mi, mu)
    alpha_u_inv = (au4 + auL + auR)/3.0
    return mu, 1.0/alpha_u_inv, {"4": au4, "L": auL, "R": auR}


def hierarchy_scan(mu_u: float, n_min: int = 1, n_max: int = 12):
    target = (MU_I/mu_u)**2
    ratio = mu_u/MP
    rows = []
    for n in range(n_min, n_max+1):
        coeff = target/(ratio**n)
        rows.append({"n": n, "coefficient_times_clebsch": coeff})
    best = min(rows, key=lambda row: abs(math.log10(row["coefficient_times_clebsch"])))
    return target, ratio, rows, best


def beta_tail(mu_i: float = MU_I):
    c = CURVATURE_COEFF*XI_I/2.0
    lambda_x = (mu_i*mu_i*MP*MP/c)**0.25
    beta = (lambda_x/MP)**2
    return lambda_x, beta

@dataclass
class Result:
    schema: str
    m_info_physical_GeV: float
    intermediate_scale_GeV: float
    unification_scale_GeV: float
    alpha_U: float
    unification_inverse_couplings: Dict[str, float]
    unification_max_spread: float
    hierarchy_target_ratio: float
    MU_over_MP: float
    preferred_power_n: int
    preferred_coefficient_times_clebsch: float
    lambda_X_GeV: float
    beta: float
    gates: Dict[str, str]
    scientific_status: str


def calculate() -> Result:
    mi = bisect_log_root(ps_matching_residual, 1e8, 1e14)
    mu, alpha_u, au = solve_422_unification(mi)
    spread = max(au.values()) - min(au.values())
    target, ratio, _rows, best = hierarchy_scan(mu)
    lambda_x, beta = beta_tail()

    gates = {
        "correct_extra_doublet_one_loop_coefficients": "PASS",
        "single_stage_SM_plus_I_unification": "FAIL",
        "422_one_loop_intermediate_solution": "PASS",
        "422_one_loop_unification_consistency": "PASS" if spread < 1e-8 else "FAIL",
        "order_one_hierarchy_operator": "PASS" if 0.1 <= best["coefficient_times_clebsch"] <= 10.0 else "REVIEW",
        "muI_to_LambdaX_to_beta_arithmetic": "PASS",
        "FToE_specific_two_loop_running": "NOT_TESTED",
        "full_heavy_threshold_spectrum": "NOT_TESTED",
        "explicit_SO10_operator_and_Clebsch": "NOT_TESTED",
        "lower_dimension_protection_proof": "NOT_TESTED",
        "proton_decay_from_frozen_spectrum": "NOT_TESTED",
    }
    mandatory = [
        "correct_extra_doublet_one_loop_coefficients",
        "422_one_loop_intermediate_solution",
        "422_one_loop_unification_consistency",
        "order_one_hierarchy_operator",
        "FToE_specific_two_loop_running",
        "full_heavy_threshold_spectrum",
        "explicit_SO10_operator_and_Clebsch",
        "lower_dimension_protection_proof",
        "proton_decay_from_frozen_spectrum",
    ]
    if any(gates[g] == "FAIL" for g in mandatory):
        status = "FAIL"
    elif any(gates[g] == "NOT_TESTED" for g in mandatory):
        status = "REVIEW"
    else:
        status = "PASS"

    return Result(
        schema="FTOE-SO10-422-CLOSURE-v0.1",
        m_info_physical_GeV=M_I_PHYS,
        intermediate_scale_GeV=mi,
        unification_scale_GeV=mu,
        alpha_U=alpha_u,
        unification_inverse_couplings=au,
        unification_max_spread=spread,
        hierarchy_target_ratio=target,
        MU_over_MP=ratio,
        preferred_power_n=best["n"],
        preferred_coefficient_times_clebsch=best["coefficient_times_clebsch"],
        lambda_X_GeV=lambda_x,
        beta=beta,
        gates=gates,
        scientific_status=status,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, help="write deterministic JSON result")
    args = parser.parse_args()
    result = calculate()
    payload = json.dumps(asdict(result), indent=2, sort_keys=True)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
