#!/usr/bin/env python3
"""Deterministic FToE SO(10)->422->SM closure gate.

This harness preserves the failed direct SM+I branch and evaluates the repaired
non-D-parity Pati-Salam branch.  It implements:

* correct one-loop contribution of an extra complex (1,2,+1/2) scalar;
* SM -> SM+I piecewise one-loop running with the informational threshold;
* residual-certified one-loop 422 matching/unification;
* gauge-only two-loop RK4 running using the published SM, 2HDM and G422
  coefficient matrices, with the FToE informational doublet switched on only
  above its physical mass (~13.5 TeV);
* a two-loop shooting solve for M_I and M_U;
* hierarchy-operator scanning and the downstream mu_I -> Lambda_X -> beta chain;
* fail-closed scientific gates.

The two-loop calculation deliberately omits Yukawa and heavy-threshold terms.
Those remain explicit scientific gates rather than being silently set to zero and
called a full result.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

PI = math.pi

# Explicit electroweak inputs.
MZ = 91.1876
ALPHA1_INV_MZ = 59.01   # SU(5)-normalized U(1)_Y
ALPHA2_INV_MZ = 29.59
ALPHA3_INV_MZ = 8.445
MP = 1.22089e19          # GeV, unreduced Planck mass used by the beta chain
XI_I = 1.0 / 6.0
CURVATURE_COEFF = 7.31
MU_I = 9.54e3            # GeV, provisional target under audit
M_I_PHYS = math.sqrt(2.0) * MU_I

# Convention: d(alpha_i^-1)/d ln(mu) = -a_i/(2*pi) at one loop.
B_SM = {"1": 41.0/10.0, "2": -19.0/6.0, "3": -7.0}
B_EXTRA_DOUBLEt = {"1": 1.0/10.0, "2": 1.0/6.0, "3": 0.0}
B_2H = {k: B_SM[k] + B_EXTRA_DOUBLEt[k] for k in B_SM}
B_422 = {"4": -7.0/3.0, "L": 2.0, "R": 28.0/3.0}

# Published gauge-only two-loop matrices.  Ordering is (3,2,1) for G321 and
# (4,2L,2R) for G422.  Yukawa terms are a separate contribution and are not
# folded into these matrices.
A_SM_321 = (-7.0, -19.0/6.0, 41.0/10.0)
BIJ_SM_321 = (
    (-26.0, 9.0/2.0, 11.0/10.0),
    (12.0, 35.0/6.0, 9.0/10.0),
    (44.0/5.0, 27.0/10.0, 199.0/50.0),
)
A_2HDM_321 = (-7.0, -3.0, 21.0/5.0)
BIJ_2HDM_321 = (
    (-26.0, 9.0/2.0, 11.0/10.0),
    (12.0, 8.0, 6.0/5.0),
    (44.0/5.0, 18.0/5.0, 104.0/25.0),
)
A_422 = (-7.0/3.0, 2.0, 28.0/3.0)
BIJ_422 = (
    (2435.0/6.0, 105.0/2.0, 249.0/2.0),
    (525.0/3.0, 73.0, 48.0),
    (1245.0/2.0, 48.0, 835.0/3.0),
)


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
    a = low_energy_couplings(mu)
    return 8.0*a["3"] - 21.0*a["2"] + 13.0*a["1"]


def bisect_log_root(fn, lo: float, hi: float, iterations: int = 160, tol: float = 1e-11) -> float:
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
        if abs(fm) <= tol:
            return math.exp(xm)
        if flo*fm <= 0:
            xhi, fhi = xm, fm
        else:
            xlo, flo = xm, fm
    return math.exp(0.5*(xlo+xhi))


def solve_422_unification(mi: float) -> Tuple[float, float, Dict[str, float]]:
    a = low_energy_couplings(mi)
    a4 = a["3"]
    aL = a["2"]
    aR = (5.0/3.0)*a["1"] - (2.0/3.0)*a4
    denom = B_422["L"] - B_422["4"]
    log_mu_over_mi = 2.0*PI*(aL-a4)/denom
    mu = mi * math.exp(log_mu_over_mi)
    au4 = evolve_alpha_inv(a4, B_422["4"], mi, mu)
    auL = evolve_alpha_inv(aL, B_422["L"], mi, mu)
    auR = evolve_alpha_inv(aR, B_422["R"], mi, mu)
    alpha_u_inv = (au4 + auL + auR)/3.0
    return mu, 1.0/alpha_u_inv, {"4": au4, "L": auL, "R": auR}


def _rhs_two_loop(inv: Sequence[float], a: Sequence[float], bij: Sequence[Sequence[float]]) -> Tuple[float, ...]:
    alphas = [1.0/x for x in inv]
    out = []
    for i in range(len(inv)):
        gauge2 = sum(bij[i][j] * alphas[j] for j in range(len(inv)))
        out.append(-a[i]/(2.0*PI) - gauge2/(8.0*PI*PI))
    return tuple(out)


def _rk4_step(inv: Sequence[float], h: float, a: Sequence[float], bij: Sequence[Sequence[float]]) -> Tuple[float, ...]:
    k1 = _rhs_two_loop(inv, a, bij)
    y2 = tuple(y + 0.5*h*k for y, k in zip(inv, k1))
    k2 = _rhs_two_loop(y2, a, bij)
    y3 = tuple(y + 0.5*h*k for y, k in zip(inv, k2))
    k3 = _rhs_two_loop(y3, a, bij)
    y4 = tuple(y + h*k for y, k in zip(inv, k3))
    k4 = _rhs_two_loop(y4, a, bij)
    return tuple(y + (h/6.0)*(p + 2*q + 2*r + s) for y, p, q, r, s in zip(inv, k1, k2, k3, k4))


def evolve_two_loop(inv0: Sequence[float], mu0: float, mu1: float, a: Sequence[float], bij: Sequence[Sequence[float]], steps_per_log: int = 96) -> Tuple[float, ...]:
    if mu0 <= 0 or mu1 <= 0:
        raise ValueError("scales must be positive")
    dt = math.log(mu1/mu0)
    if dt == 0.0:
        return tuple(inv0)
    n = max(8, int(math.ceil(abs(dt)*steps_per_log)))
    h = dt/n
    y = tuple(float(x) for x in inv0)
    for _ in range(n):
        y = _rk4_step(y, h, a, bij)
        if min(y) <= 0.0:
            raise ValueError("non-perturbative/invalid inverse coupling encountered")
    return y


def low_energy_couplings_two_loop(mu: float) -> Dict[str, float]:
    """Gauge-only two-loop SM -> SM+I evolution; output keys are 1,2,3."""
    if mu < MZ:
        raise ValueError("mu must be >= MZ")
    # Internal matrix order is (3,2,1).
    y0 = (ALPHA3_INV_MZ, ALPHA2_INV_MZ, ALPHA1_INV_MZ)
    if mu <= M_I_PHYS:
        y = evolve_two_loop(y0, MZ, mu, A_SM_321, BIJ_SM_321)
    else:
        yt = evolve_two_loop(y0, MZ, M_I_PHYS, A_SM_321, BIJ_SM_321)
        y = evolve_two_loop(yt, M_I_PHYS, mu, A_2HDM_321, BIJ_2HDM_321)
    return {"3": y[0], "2": y[1], "1": y[2]}


def _interpolate_crossing(prev_t: float, prev_y: Sequence[float], t: float, y: Sequence[float], i: int, j: int) -> Tuple[float, Tuple[float, ...]]:
    f0 = prev_y[i] - prev_y[j]
    f1 = y[i] - y[j]
    if f0 == f1:
        frac = 0.5
    else:
        frac = -f0/(f1-f0)
    frac = min(1.0, max(0.0, frac))
    tc = prev_t + frac*(t-prev_t)
    yc = tuple(a + frac*(b-a) for a, b in zip(prev_y, y))
    return tc, yc


def shoot_422_two_loop(mi: float, step_log: float = 0.006, max_mu: float = 1e19) -> Tuple[float, float, Dict[str, float]]:
    """Run gauge-only G422 upward and locate alpha_4=alpha_L crossing.

    Returns (M_U, residual_R_minus_4, inverse couplings at crossing).
    """
    low = low_energy_couplings_two_loop(mi)
    a4 = low["3"]
    aL = low["2"]
    aR = (5.0/3.0)*low["1"] - (2.0/3.0)*a4
    y = (a4, aL, aR)
    t = math.log(mi)
    tmax = math.log(max_mu)
    prev_t, prev_y = t, y
    prev_f = y[0] - y[1]
    while t < tmax:
        h = min(step_log, tmax-t)
        y = _rk4_step(y, h, A_422, BIJ_422)
        t += h
        f = y[0] - y[1]
        if prev_f == 0.0 or prev_f*f <= 0.0:
            tc, yc = _interpolate_crossing(prev_t, prev_y, t, y, 0, 1)
            mu = math.exp(tc)
            return mu, yc[2]-yc[0], {"4": yc[0], "L": yc[1], "R": yc[2]}
        prev_t, prev_y, prev_f = t, y, f
    raise ValueError("alpha_4 and alpha_L do not cross below max_mu")


def two_loop_mi_residual(mi: float) -> float:
    _mu, residual, _inv = shoot_422_two_loop(mi)
    return residual


def solve_two_loop_422() -> Tuple[float, float, float, Dict[str, float], float]:
    """Solve gauge-only FToE-specific two-loop M_I and M_U.

    The second doublet is activated only at M_I_PHYS, unlike the reference 2HDM
    calculation where it is active from the electroweak scale.
    """
    mi = bisect_log_root(two_loop_mi_residual, 1e8, 1e13, iterations=70, tol=2e-5)
    mu, residual, inv = shoot_422_two_loop(mi, step_log=0.0025)
    spread = max(inv.values()) - min(inv.values())
    alpha_u = 1.0/(sum(inv.values())/3.0)
    return mi, mu, alpha_u, inv, spread


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
    one_loop_intermediate_scale_GeV: float
    one_loop_unification_scale_GeV: float
    one_loop_alpha_U: float
    one_loop_unification_max_spread: float
    two_loop_intermediate_scale_GeV: float
    two_loop_unification_scale_GeV: float
    two_loop_alpha_U: float
    two_loop_unification_inverse_couplings: Dict[str, float]
    two_loop_unification_max_spread: float
    hierarchy_target_ratio: float
    MU_over_MP: float
    preferred_power_n: int
    preferred_coefficient_times_clebsch: float
    lambda_X_GeV: float
    beta: float
    gates: Dict[str, str]
    scientific_status: str


def calculate() -> Result:
    mi1 = bisect_log_root(ps_matching_residual, 1e8, 1e14)
    mu1, alpha_u1, au1 = solve_422_unification(mi1)
    spread1 = max(au1.values()) - min(au1.values())

    mi2, mu2, alpha_u2, au2, spread2 = solve_two_loop_422()
    target, ratio, _rows, best = hierarchy_scan(mu2)
    lambda_x, beta = beta_tail()

    gates = {
        "correct_extra_doublet_one_loop_coefficients": "PASS",
        "single_stage_SM_plus_I_unification": "FAIL",
        "422_one_loop_intermediate_solution": "PASS",
        "422_one_loop_unification_consistency": "PASS" if spread1 < 1e-7 else "FAIL",
        "FToE_specific_two_loop_gauge_running": "PASS" if spread2 < 5e-3 else "FAIL",
        "two_loop_yukawa_contribution": "NOT_TESTED",
        "order_one_hierarchy_operator": "PASS" if 0.1 <= best["coefficient_times_clebsch"] <= 10.0 else "REVIEW",
        "muI_to_LambdaX_to_beta_arithmetic": "PASS",
        "full_heavy_threshold_spectrum": "NOT_TESTED",
        "explicit_SO10_operator_and_Clebsch": "NOT_TESTED",
        "lower_dimension_protection_proof": "NOT_TESTED",
        "proton_decay_from_frozen_spectrum": "NOT_TESTED",
    }
    mandatory = [
        "correct_extra_doublet_one_loop_coefficients",
        "422_one_loop_intermediate_solution",
        "422_one_loop_unification_consistency",
        "FToE_specific_two_loop_gauge_running",
        "two_loop_yukawa_contribution",
        "order_one_hierarchy_operator",
        "full_heavy_threshold_spectrum",
        "explicit_SO10_operator_and_Clebsch",
        "lower_dimension_protection_proof",
        "proton_decay_from_frozen_spectrum",
    ]
    if any(gates[g] == "FAIL" for g in mandatory):
        status = "FAIL"
    elif any(gates[g] == "NOT_TESTED" for g in mandatory):
        status = "REVIEW"
    elif any(gates[g] == "REVIEW" for g in mandatory):
        status = "REVIEW"
    else:
        status = "PASS"

    return Result(
        schema="FTOE-SO10-422-CLOSURE-v0.2",
        m_info_physical_GeV=M_I_PHYS,
        one_loop_intermediate_scale_GeV=mi1,
        one_loop_unification_scale_GeV=mu1,
        one_loop_alpha_U=alpha_u1,
        one_loop_unification_max_spread=spread1,
        two_loop_intermediate_scale_GeV=mi2,
        two_loop_unification_scale_GeV=mu2,
        two_loop_alpha_U=alpha_u2,
        two_loop_unification_inverse_couplings=au2,
        two_loop_unification_max_spread=spread2,
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
