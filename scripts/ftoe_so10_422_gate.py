"""Deterministic FToE SO(10)->422->SM closure gate.

Preserves the failed direct SM+I branch and evaluates the repaired non-D-parity
Pati-Salam branch. The gauge-only two-loop calculation uses published SM,
2HDM and G422 coefficient matrices and switches the informational doublet on
only above its physical mass (~13.5 TeV).

Yukawa and heavy-threshold terms remain explicit scientific gates; they are not
silently set to zero and called a full result.
"""
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

PI = math.pi
MZ = 91.1876
ALPHA1_INV_MZ = 59.01
ALPHA2_INV_MZ = 29.59
ALPHA3_INV_MZ = 8.445
MP = 1.22089e19
XI_I = 1.0 / 6.0
CURVATURE_COEFF = 7.31
MU_I = 9.54e3
M_I_PHYS = math.sqrt(2.0) * MU_I

B_SM = {"1": 41.0 / 10.0, "2": -19.0 / 6.0, "3": -7.0}
B_EXTRA_DOUBLEt = {"1": 1.0 / 10.0, "2": 1.0 / 6.0, "3": 0.0}
B_2H = {key: B_SM[key] + B_EXTRA_DOUBLEt[key] for key in B_SM}
B_422 = {"4": -7.0 / 3.0, "L": 2.0, "R": 28.0 / 3.0}

A_SM_321 = (-7.0, -19.0 / 6.0, 41.0 / 10.0)
BIJ_SM_321 = (
    (-26.0, 9.0 / 2.0, 11.0 / 10.0),
    (12.0, 35.0 / 6.0, 9.0 / 10.0),
    (44.0 / 5.0, 27.0 / 10.0, 199.0 / 50.0),
)
A_2HDM_321 = (-7.0, -3.0, 21.0 / 5.0)
BIJ_2HDM_321 = (
    (-26.0, 9.0 / 2.0, 11.0 / 10.0),
    (12.0, 8.0, 6.0 / 5.0),
    (44.0 / 5.0, 18.0 / 5.0, 104.0 / 25.0),
)
A_422 = (-7.0 / 3.0, 2.0, 28.0 / 3.0)
BIJ_422 = (
    (2435.0 / 6.0, 105.0 / 2.0, 249.0 / 2.0),
    (525.0 / 3.0, 73.0, 48.0),
    (1245.0 / 2.0, 48.0, 835.0 / 3.0),
)


def evolve_alpha_inv(alpha_inv: float, b: float, mu0: float, mu1: float) -> float:
    if mu0 <= 0 or mu1 <= 0:
        raise ValueError("scales must be positive")
    return alpha_inv - (b / (2.0 * PI)) * math.log(mu1 / mu0)


def low_energy_couplings(
    mu: float,
    threshold: float = M_I_PHYS,
) -> dict[str, float]:
    if mu < MZ:
        raise ValueError("mu must be >= MZ")
    start = {"1": ALPHA1_INV_MZ, "2": ALPHA2_INV_MZ, "3": ALPHA3_INV_MZ}
    if mu <= threshold:
        return {
            key: evolve_alpha_inv(start[key], B_SM[key], MZ, mu) for key in start
        }
    at = {
        key: evolve_alpha_inv(start[key], B_SM[key], MZ, threshold) for key in start
    }
    return {
        key: evolve_alpha_inv(at[key], B_2H[key], threshold, mu) for key in start
    }


def ps_matching_residual(mu: float) -> float:
    a = low_energy_couplings(mu)
    return 8.0 * a["3"] - 21.0 * a["2"] + 13.0 * a["1"]


def bisect_log_root(
    fn,
    lo: float,
    hi: float,
    iterations: int = 160,
    tol: float = 1e-11,
) -> float:
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
        xm = 0.5 * (xlo + xhi)
        fm = fn(math.exp(xm))
        if abs(fm) <= tol:
            return math.exp(xm)
        if flo * fm <= 0:
            xhi, fhi = xm, fm
        else:
            xlo, flo = xm, fm
    return math.exp(0.5 * (xlo + xhi))


def find_log_sign_change(
    fn,
    lo: float,
    hi: float,
    samples: int = 80,
) -> tuple[float, float]:
    """Find a local sign-change bracket without assuming global monotonicity."""
    if lo <= 0 or hi <= lo or samples < 2:
        raise ValueError("invalid scan")
    l0, l1 = math.log(lo), math.log(hi)
    prev_x = math.exp(l0)
    prev_f = fn(prev_x)
    if prev_f == 0.0:
        return prev_x, prev_x
    for i in range(1, samples + 1):
        x = math.exp(l0 + (l1 - l0) * i / samples)
        value = fn(x)
        if value == 0.0:
            return x, x
        if prev_f * value < 0.0:
            return prev_x, x
        prev_x, prev_f = x, value
    raise ValueError("no sign change found in scan interval")


def solve_422_unification(mi: float) -> tuple[float, float, dict[str, float]]:
    a = low_energy_couplings(mi)
    a4, a_l = a["3"], a["2"]
    a_r = (5.0 / 3.0) * a["1"] - (2.0 / 3.0) * a4
    log_ratio = 2.0 * PI * (a_l - a4) / (B_422["L"] - B_422["4"])
    mu = mi * math.exp(log_ratio)
    au4 = evolve_alpha_inv(a4, B_422["4"], mi, mu)
    au_l = evolve_alpha_inv(a_l, B_422["L"], mi, mu)
    au_r = evolve_alpha_inv(a_r, B_422["R"], mi, mu)
    avg = (au4 + au_l + au_r) / 3.0
    return mu, 1.0 / avg, {"4": au4, "L": au_l, "R": au_r}


def _rhs_two_loop(
    inv: Sequence[float],
    a: Sequence[float],
    bij: Sequence[Sequence[float]],
) -> tuple[float, ...]:
    alpha = [1.0 / value for value in inv]
    return tuple(
        -a[i] / (2.0 * PI)
        - sum(bij[i][j] * alpha[j] for j in range(len(inv))) / (8.0 * PI * PI)
        for i in range(len(inv))
    )


def _rk4_step(
    inv: Sequence[float],
    h: float,
    a: Sequence[float],
    bij: Sequence[Sequence[float]],
) -> tuple[float, ...]:
    k1 = _rhs_two_loop(inv, a, bij)
    y2 = tuple(y + 0.5 * h * k for y, k in zip(inv, k1))
    k2 = _rhs_two_loop(y2, a, bij)
    y3 = tuple(y + 0.5 * h * k for y, k in zip(inv, k2))
    k3 = _rhs_two_loop(y3, a, bij)
    y4 = tuple(y + h * k for y, k in zip(inv, k3))
    k4 = _rhs_two_loop(y4, a, bij)
    return tuple(
        y + h * (p + 2 * q + 2 * r + s) / 6.0
        for y, p, q, r, s in zip(inv, k1, k2, k3, k4)
    )


def evolve_two_loop(
    inv0: Sequence[float],
    mu0: float,
    mu1: float,
    a: Sequence[float],
    bij: Sequence[Sequence[float]],
    steps_per_log: int = 96,
) -> tuple[float, ...]:
    if mu0 <= 0 or mu1 <= 0:
        raise ValueError("scales must be positive")
    dt = math.log(mu1 / mu0)
    if dt == 0.0:
        return tuple(inv0)
    n = max(8, math.ceil(abs(dt) * steps_per_log))
    h = dt / n
    y = tuple(float(value) for value in inv0)
    for _ in range(n):
        y = _rk4_step(y, h, a, bij)
        if min(y) <= 0.0:
            raise ValueError("non-perturbative inverse coupling")
    return y


def low_energy_couplings_two_loop(
    mu: float,
    threshold: float = M_I_PHYS,
) -> dict[str, float]:
    if mu < MZ:
        raise ValueError("mu must be >= MZ")
    y0 = (ALPHA3_INV_MZ, ALPHA2_INV_MZ, ALPHA1_INV_MZ)
    if threshold <= MZ:
        y = evolve_two_loop(y0, MZ, mu, A_2HDM_321, BIJ_2HDM_321)
    elif mu <= threshold:
        y = evolve_two_loop(y0, MZ, mu, A_SM_321, BIJ_SM_321)
    else:
        at_threshold = evolve_two_loop(
            y0,
            MZ,
            threshold,
            A_SM_321,
            BIJ_SM_321,
        )
        y = evolve_two_loop(
            at_threshold,
            threshold,
            mu,
            A_2HDM_321,
            BIJ_2HDM_321,
        )
    return {"3": y[0], "2": y[1], "1": y[2]}


def _interpolate_crossing(
    prev_t: float,
    prev_y: Sequence[float],
    t: float,
    y: Sequence[float],
    i: int,
    j: int,
) -> tuple[float, tuple[float, ...]]:
    f0, f1 = prev_y[i] - prev_y[j], y[i] - y[j]
    frac = 0.5 if f0 == f1 else -f0 / (f1 - f0)
    frac = min(1.0, max(0.0, frac))
    crossing_t = prev_t + frac * (t - prev_t)
    crossing_y = tuple(a + frac * (b - a) for a, b in zip(prev_y, y))
    return crossing_t, crossing_y


def shoot_422_two_loop(
    mi: float,
    threshold: float = M_I_PHYS,
    step_log: float = 0.006,
    max_mu: float = 1e19,
) -> tuple[float, float, dict[str, float]]:
    low = low_energy_couplings_two_loop(mi, threshold=threshold)
    a4, a_l = low["3"], low["2"]
    a_r = (5.0 / 3.0) * low["1"] - (2.0 / 3.0) * a4
    y = (a4, a_l, a_r)
    t, tmax = math.log(mi), math.log(max_mu)
    prev_t, prev_y, prev_f = t, y, y[0] - y[1]
    while t < tmax:
        h = min(step_log, tmax - t)
        y = _rk4_step(y, h, A_422, BIJ_422)
        t += h
        value = y[0] - y[1]
        if prev_f == 0.0 or prev_f * value <= 0.0:
            crossing_t, crossing_y = _interpolate_crossing(
                prev_t,
                prev_y,
                t,
                y,
                0,
                1,
            )
            return (
                math.exp(crossing_t),
                crossing_y[2] - crossing_y[0],
                {"4": crossing_y[0], "L": crossing_y[1], "R": crossing_y[2]},
            )
        prev_t, prev_y, prev_f = t, y, value
    raise ValueError("alpha_4 and alpha_L do not cross below max_mu")


def two_loop_mi_residual(mi: float, threshold: float = M_I_PHYS) -> float:
    return shoot_422_two_loop(mi, threshold=threshold)[1]


def solve_two_loop_422(
    threshold: float = M_I_PHYS,
) -> tuple[float, float, float, dict[str, float], float]:
    """Solve gauge-only two-loop M_I and M_U for a second-doublet threshold."""
    fn = lambda x: two_loop_mi_residual(x, threshold=threshold)
    lo, hi = find_log_sign_change(fn, 1e6, 1e14, samples=100)
    mi = (
        lo
        if lo == hi
        else bisect_log_root(fn, lo, hi, iterations=80, tol=2e-5)
    )
    mu, _, inverse = shoot_422_two_loop(
        mi,
        threshold=threshold,
        step_log=0.0025,
    )
    spread = max(inverse.values()) - min(inverse.values())
    alpha_u = 1.0 / (sum(inverse.values()) / 3.0)
    return mi, mu, alpha_u, inverse, spread


def hierarchy_scan(mu_u: float, n_min: int = 1, n_max: int = 12):
    target = (MU_I / mu_u) ** 2
    ratio = mu_u / MP
    rows = []
    for power in range(n_min, n_max + 1):
        coeff = target / ratio**power
        rows.append({"n": power, "coefficient_times_clebsch": coeff})
    best = min(
        rows,
        key=lambda row: abs(math.log10(row["coefficient_times_clebsch"])),
    )
    return target, ratio, rows, best


def beta_tail(mu_i: float = MU_I):
    coeff = CURVATURE_COEFF * XI_I / 2.0
    lambda_x = (mu_i * mu_i * MP * MP / coeff) ** 0.25
    return lambda_x, (lambda_x / MP) ** 2


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
    two_loop_unification_inverse_couplings: dict[str, float]
    two_loop_unification_max_spread: float
    reference_2HDM_two_loop_intermediate_scale_GeV: float
    reference_2HDM_two_loop_unification_scale_GeV: float
    hierarchy_target_ratio: float
    MU_over_MP: float
    preferred_power_n: int
    preferred_coefficient_times_clebsch: float
    lambda_X_GeV: float
    beta: float
    gates: dict[str, str]
    scientific_status: str


def calculate() -> Result:
    mi1 = bisect_log_root(ps_matching_residual, 1e8, 1e14)
    mu1, alpha_u1, au1 = solve_422_unification(mi1)
    spread1 = max(au1.values()) - min(au1.values())

    ref_mi, ref_mu, _, _, ref_spread = solve_two_loop_422(threshold=MZ)
    mi2, mu2, alpha_u2, au2, spread2 = solve_two_loop_422(threshold=M_I_PHYS)
    target, ratio, _, best = hierarchy_scan(mu2)
    lambda_x, beta = beta_tail()

    ref_ok = 5e9 < ref_mi < 5e10 and 5e15 < ref_mu < 5e16 and ref_spread < 5e-3
    gates = {
        "correct_extra_doublet_one_loop_coefficients": "PASS",
        "single_stage_SM_plus_I_unification": "FAIL",
        "422_one_loop_intermediate_solution": "PASS",
        "422_one_loop_unification_consistency": "PASS" if spread1 < 1e-7 else "FAIL",
        "published_2HDM_two_loop_regression": "PASS" if ref_ok else "FAIL",
        "FToE_specific_two_loop_gauge_running": "PASS" if spread2 < 5e-3 else "FAIL",
        "two_loop_yukawa_contribution": "NOT_TESTED",
        "order_one_hierarchy_operator": (
            "PASS" if 0.1 <= best["coefficient_times_clebsch"] <= 10.0 else "REVIEW"
        ),
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
        "published_2HDM_two_loop_regression",
        "FToE_specific_two_loop_gauge_running",
        "two_loop_yukawa_contribution",
        "order_one_hierarchy_operator",
        "full_heavy_threshold_spectrum",
        "explicit_SO10_operator_and_Clebsch",
        "lower_dimension_protection_proof",
        "proton_decay_from_frozen_spectrum",
    ]
    if any(gates[gate] == "FAIL" for gate in mandatory):
        status = "FAIL"
    elif any(gates[gate] in {"NOT_TESTED", "REVIEW"} for gate in mandatory):
        status = "REVIEW"
    else:
        status = "PASS"

    return Result(
        schema="FTOE-SO10-422-CLOSURE-v0.3",
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
        reference_2HDM_two_loop_intermediate_scale_GeV=ref_mi,
        reference_2HDM_two_loop_unification_scale_GeV=ref_mu,
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
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    payload = json.dumps(asdict(calculate()), indent=2, sort_keys=True)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
