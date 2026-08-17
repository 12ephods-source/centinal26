"""Conditioning and adaptive continuation gate for FToE SO(10)->G422 roots.

This extends the verified local survival test without promoting gauge matching to
full physical closure. It computes invariant 2-norm conditioning diagnostics and
implicit parameter sensitivities, then continues the connected physical branch
outward in alpha_s until a certified termination event or a declared safety cap.
A safety-cap hit is reported as unresolved, never as a physical boundary.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SURVIVAL_PATH = HERE / "ftoe_so10_parametric_survival.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_survival_ext", SURVIVAL_PATH)
assert spec and spec.loader
survival = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = survival
spec.loader.exec_module(survival)
roots2d = survival.roots2d

ALPHA_CENTER = survival.ALPHA_S_CENTER
ALPHA_STEP = 5e-4
ALPHA_MIN_CAP = 0.105
ALPHA_MAX_CAP = 0.135
PARAM_STEP = 2e-5
ENUMERATION_STRIDE = 0.002


def singular_values_2x2(j11: float, j12: float, j21: float, j22: float) -> tuple[float, float]:
    # Eigenvalues of J^T J, evaluated analytically to avoid an external dependency.
    a = j11 * j11 + j21 * j21
    b = j11 * j12 + j21 * j22
    d = j12 * j12 + j22 * j22
    tr = a + d
    disc = max(0.0, (a - d) * (a - d) + 4.0 * b * b)
    root = math.sqrt(disc)
    lmax = max(0.0, 0.5 * (tr + root))
    lmin = max(0.0, 0.5 * (tr - root))
    return math.sqrt(lmax), math.sqrt(lmin)


def solve_linear_2x2(j: dict, rhs1: float, rhs2: float) -> tuple[float, float]:
    det = j["j11"] * j["j22"] - j["j12"] * j["j21"]
    if abs(det) < 1e-14:
        raise ValueError("singular Jacobian")
    x = (rhs1 * j["j22"] - j["j12"] * rhs2) / det
    y = (j["j11"] * rhs2 - rhs1 * j["j21"]) / det
    return x, y


def residual_at(root: dict, threshold: float, alpha_s: float) -> tuple[float, float]:
    survival.set_alpha_s(alpha_s)
    x = math.log(root["MI_GeV"])
    y = math.log(root["MU_GeV"])
    f1, f2, _ = roots2d.residual_xy(x, y, threshold, steps_per_log=120)
    return f1, f2


def conditioning(root: dict, threshold: float, alpha_s: float) -> dict:
    survival.set_alpha_s(alpha_s)
    j = survival.jacobian_at(root, threshold)
    smax, smin = singular_values_2x2(j["j11"], j["j12"], j["j21"], j["j22"])
    kappa = math.inf if smin == 0.0 else smax / smin

    da = PARAM_STEP
    fp = residual_at(root, threshold, alpha_s + da)
    fm = residual_at(root, threshold, alpha_s - da)
    dF_da = ((fp[0] - fm[0]) / (2.0 * da), (fp[1] - fm[1]) / (2.0 * da))
    dz_da = solve_linear_2x2(j, -dF_da[0], -dF_da[1])

    dt = PARAM_STEP
    tp = threshold * math.exp(dt)
    tm = threshold * math.exp(-dt)
    fp_t = residual_at(root, tp, alpha_s)
    fm_t = residual_at(root, tm, alpha_s)
    dF_dlogt = ((fp_t[0] - fm_t[0]) / (2.0 * dt), (fp_t[1] - fm_t[1]) / (2.0 * dt))
    dz_dlogt = solve_linear_2x2(j, -dF_dlogt[0], -dF_dlogt[1])

    return {
        "sigma_max": smax,
        "sigma_min": smin,
        "kappa_2": kappa,
        "d_lnMI_d_alpha_s": dz_da[0],
        "d_lnMU_d_alpha_s": dz_da[1],
        "d_lnMI_d_ln_threshold": dz_dlogt[0],
        "d_lnMU_d_ln_threshold": dz_dlogt[1],
        "jacobian_det": j["det"],
    }


def certified_root(alpha_s: float, threshold: float, seed: dict | None) -> dict | None:
    root = survival.solve_seeded(alpha_s, threshold, seed)
    if root is None:
        return None
    if not (roots2d.core.MZ < threshold < root["MI_GeV"] < root["MU_GeV"] < 1e19):
        return None
    if not (0.0 < root["alpha_U"] < 1.0):
        return None
    if root["max_spread"] > 1e-5:
        return None
    return root


def enumerate_roots(alpha_s: float, threshold: float) -> list[dict]:
    survival.set_alpha_s(alpha_s)
    return roots2d.solve_all(threshold, nx=5, ny=5)


def continue_direction(threshold: float, direction: int) -> dict:
    if direction not in (-1, 1):
        raise ValueError("direction must be +/-1")
    seed = certified_root(ALPHA_CENTER, threshold, None)
    if seed is None:
        return {"termination": "NO_ROOT_AT_CENTER", "points": []}
    points = []
    alpha = ALPHA_CENTER
    next_enum = ALPHA_CENTER
    cap = ALPHA_MIN_CAP if direction < 0 else ALPHA_MAX_CAP

    while (alpha > cap if direction < 0 else alpha < cap):
        alpha_next = alpha + direction * ALPHA_STEP
        if direction < 0:
            alpha_next = max(alpha_next, cap)
        else:
            alpha_next = min(alpha_next, cap)
        root = certified_root(alpha_next, threshold, seed)
        if root is None:
            return {
                "termination": "NO_CERTIFIED_ROOT",
                "last_root_alpha_s": alpha,
                "first_failed_alpha_s": alpha_next,
                "points": points,
            }
        diag = conditioning(root, threshold, alpha_next)
        row = {
            "alpha_s_MZ": alpha_next,
            "MI_GeV": root["MI_GeV"],
            "MU_GeV": root["MU_GeV"],
            "alpha_U": root["alpha_U"],
            "max_spread": root["max_spread"],
            **diag,
        }
        if abs(alpha_next - next_enum) >= ENUMERATION_STRIDE - 1e-12 or alpha_next == cap:
            roots = enumerate_roots(alpha_next, threshold)
            row["enumerated_root_count"] = len(roots)
            row["enumerated_roots"] = [
                {"MI_GeV": r["MI_GeV"], "MU_GeV": r["MU_GeV"], "alpha_U": r["alpha_U"]}
                for r in roots
            ]
            next_enum = alpha_next
        points.append(row)
        seed = root
        alpha = alpha_next
        if alpha == cap:
            return {
                "termination": "SAFETY_CAP_REACHED",
                "cap_alpha_s": cap,
                "points": points,
            }
    return {"termination": "SAFETY_CAP_REACHED", "cap_alpha_s": cap, "points": points}


def summarize_direction(result: dict) -> dict:
    points = result.get("points", [])
    out = {k: v for k, v in result.items() if k != "points"}
    out["point_count"] = len(points)
    if points:
        out["minimum_sigma_min"] = min(p["sigma_min"] for p in points)
        out["maximum_kappa_2"] = max(p["kappa_2"] for p in points)
        out["maximum_abs_d_lnMU_d_alpha_s"] = max(abs(p["d_lnMU_d_alpha_s"]) for p in points)
        out["maximum_abs_d_lnMI_d_alpha_s"] = max(abs(p["d_lnMI_d_alpha_s"]) for p in points)
    return out


def calculate() -> dict:
    nominal = roots2d.core.M_I_PHYS
    scans = []
    for factor in survival.THRESHOLD_FACTORS:
        threshold = nominal * factor
        center = certified_root(ALPHA_CENTER, threshold, None)
        if center is None:
            scans.append({"threshold_factor": factor, "status": "NO_ROOT_AT_CENTER"})
            continue
        center_diag = conditioning(center, threshold, ALPHA_CENTER)
        lower = continue_direction(threshold, -1)
        upper = continue_direction(threshold, +1)
        scans.append({
            "threshold_factor": factor,
            "threshold_GeV": threshold,
            "center": {**center, **center_diag},
            "lower": lower,
            "upper": upper,
            "lower_summary": summarize_direction(lower),
            "upper_summary": summarize_direction(upper),
        })
    return {
        "schema": "FTOE-SO10-CONDITIONING-CONTINUATION-v0.1",
        "alpha_s_center": ALPHA_CENTER,
        "alpha_step": ALPHA_STEP,
        "alpha_caps": [ALPHA_MIN_CAP, ALPHA_MAX_CAP],
        "threshold_factors": list(survival.THRESHOLD_FACTORS),
        "scans": scans,
        "scientific_status": "REVIEW",
        "interpretation": {
            "SAFETY_CAP_REACHED": "branch survived to computational cap; physical termination not located",
            "NO_CERTIFIED_ROOT": "continuation lost a certified admissible root; requires local boundary refinement before physical interpretation",
        },
        "notes": [
            "Conditioning uses analytic singular values of the 2x2 Jacobian; raw determinant is retained only for provenance.",
            "Sensitivities use dz/dp = -J^{-1} dF/dp with central finite differences on the original RK4 residual map.",
            "Periodic solve_all enumeration checks for secondary real roots; disconnected regions outside the sampled continuation corridor are not claimed exhausted.",
            "Proton decay remains excluded from this gate until a frozen heavy spectrum fixes the decay map independently.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = calculate()
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
