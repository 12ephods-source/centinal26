"""Parametric survival boundary for the two-loop SO(10)->G422 matching roots.

The two-loop residuals are produced by RK4 integration and are not polynomial in
x=ln(M_I), y=ln(M_U). Therefore no exact algebraic resultant/discriminant exists
without replacing the validated equations by a surrogate. The invariant fold
condition on the original equations is instead

    F1(x,y;p)=0, F2(x,y;p)=0, det(d(F1,F2)/d(x,y))=0,

where p=(alpha_s(M_Z), m_info). A root can also leave the declared physical
search domain. This script follows the certified 2D root by continuation and
records its Jacobian determinant; it never falls back to the 1D shooting path.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOTS_PATH = HERE / "ftoe_so10_422_2d_roots.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_422_2d_survival", ROOTS_PATH)
assert spec and spec.loader
roots2d = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = roots2d
spec.loader.exec_module(roots2d)

ALPHA_S_CENTER = 0.1181
ALPHA_S_SIGMA = 0.0009
THRESHOLD_FACTORS = (0.5, 0.75, 1.0, 1.5, 2.0)
ALPHA_STEP = 0.0001
ALPHA_MARGIN = 0.0020
DET_STEP = 2e-5
DET_FOLD_TOL = 1e-7


def set_alpha_s(alpha_s: float) -> None:
    if alpha_s <= 0.0:
        raise ValueError("alpha_s must be positive")
    roots2d.core.ALPHA3_INV_MZ = 1.0 / alpha_s


def jacobian_at(root: dict, threshold: float, h: float = DET_STEP) -> dict:
    x = math.log(root["MI_GeV"])
    y = math.log(root["MU_GeV"])
    f1, f2, _ = roots2d.residual_xy(x, y, threshold, steps_per_log=120)
    fx = roots2d.residual_xy(x + h, y, threshold, steps_per_log=120)
    fy = roots2d.residual_xy(x, y + h, threshold, steps_per_log=120)
    j11 = (fx[0] - f1) / h
    j21 = (fx[1] - f2) / h
    j12 = (fy[0] - f1) / h
    j22 = (fy[1] - f2) / h
    det = j11 * j22 - j12 * j21
    return {
        "j11": j11,
        "j12": j12,
        "j21": j21,
        "j22": j22,
        "det": det,
        "abs_det": abs(det),
        "near_fold": abs(det) <= DET_FOLD_TOL,
    }


def solve_seeded(alpha_s: float, threshold: float, seed: dict | None) -> dict | None:
    set_alpha_s(alpha_s)
    if seed is not None:
        root = roots2d.newton(
            math.log(seed["MI_GeV"]),
            math.log(seed["MU_GeV"]),
            threshold,
        )
        if root is not None:
            return root
    candidates = roots2d.solve_all(threshold, nx=3, ny=3)
    if not candidates:
        return None
    return min(candidates, key=lambda row: abs(row["log10_MU"] - 16.3))


def trace_alpha(threshold: float, center: float = ALPHA_S_CENTER) -> list[dict]:
    start = solve_seeded(center, threshold, None)
    if start is None:
        return [{"alpha_s_MZ": center, "status": "NO_ROOT"}]
    rows = []
    for direction in (-1, 1):
        seed = start
        nmax = round(ALPHA_MARGIN / ALPHA_STEP)
        for k in range(nmax + 1):
            alpha_s = center + direction * k * ALPHA_STEP
            if direction == 1 and k == 0:
                continue
            root = solve_seeded(alpha_s, threshold, seed)
            if root is None:
                rows.append({"alpha_s_MZ": alpha_s, "status": "NO_ROOT"})
                break
            j = jacobian_at(root, threshold)
            rows.append(
                {
                    "alpha_s_MZ": alpha_s,
                    "status": "ROOT",
                    "MI_GeV": root["MI_GeV"],
                    "MU_GeV": root["MU_GeV"],
                    "alpha_U": root["alpha_U"],
                    "max_spread": root["max_spread"],
                    "jacobian_det": j["det"],
                    "jacobian_abs_det": j["abs_det"],
                    "near_fold": j["near_fold"],
                }
            )
            seed = root
    rows.sort(key=lambda row: row["alpha_s_MZ"])
    return rows


def summarize(rows: list[dict]) -> dict:
    solved = [row for row in rows if row["status"] == "ROOT"]
    if not solved:
        return {"root_count": 0, "survival_width": 0.0, "covers_experimental_band": False}
    lo = min(row["alpha_s_MZ"] for row in solved)
    hi = max(row["alpha_s_MZ"] for row in solved)
    exp_lo = ALPHA_S_CENTER - ALPHA_S_SIGMA
    exp_hi = ALPHA_S_CENTER + ALPHA_S_SIGMA
    return {
        "root_count": len(solved),
        "alpha_s_survival_min": lo,
        "alpha_s_survival_max": hi,
        "survival_width": hi - lo,
        "experimental_band_min": exp_lo,
        "experimental_band_max": exp_hi,
        "experimental_width": 2.0 * ALPHA_S_SIGMA,
        "covers_experimental_band": lo <= exp_lo and hi >= exp_hi,
        "minimum_abs_jacobian_det": min(row["jacobian_abs_det"] for row in solved),
        "near_fold_seen": any(row["near_fold"] for row in solved),
    }


def calculate() -> dict:
    nominal = roots2d.core.M_I_PHYS
    scans = []
    for factor in THRESHOLD_FACTORS:
        threshold = nominal * factor
        rows = trace_alpha(threshold)
        scans.append(
            {
                "threshold_factor": factor,
                "threshold_GeV": threshold,
                "summary": summarize(rows),
                "points": rows,
            }
        )
    nominal_scan = next(row for row in scans if row["threshold_factor"] == 1.0)
    summary = nominal_scan["summary"]
    verdict = (
        "SURVIVES_EXPERIMENTAL_ALPHA_S_BAND"
        if summary.get("covers_experimental_band")
        else "FAIL_PARAMETRIC_SURVIVAL_ALPHA_S"
    )
    return {
        "schema": "FTOE-SO10-PARAMETRIC-SURVIVAL-v0.1",
        "method": "implicit-function continuation on original two-loop RK4 residuals",
        "fold_condition": "F1=F2=0 and det(d(F1,F2)/d(lnMI,lnMU))=0",
        "algebraic_resultant_status": "NOT_APPLICABLE_TO_NONPOLYNOMIAL_RK4_MAP_WITHOUT_SURROGATE",
        "alpha_s_center": ALPHA_S_CENTER,
        "alpha_s_sigma": ALPHA_S_SIGMA,
        "alpha_step": ALPHA_STEP,
        "threshold_factors": list(THRESHOLD_FACTORS),
        "nominal_threshold_verdict": verdict,
        "scans": scans,
        "scientific_status": "REVIEW" if verdict.startswith("SURVIVES") else "FAIL",
        "notes": [
            "A NO_ROOT point is a continuation/search-domain result and is not called a complex root.",
            "A fold is identified only by a small Jacobian determinant on an otherwise certified real root.",
            "The experimental comparison is against the preregistered +/-0.0009 alpha_s band.",
            "Threshold-factor dependence is reported separately; no threshold is selected after observing survival.",
        ],
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
