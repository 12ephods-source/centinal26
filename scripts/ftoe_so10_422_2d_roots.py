#!/usr/bin/env python3
"""Branch-complete 2D root solver for two-loop G422 gauge unification.

Solves the simultaneous equations
  alpha4^-1(MU) - alphaL^-1(MU) = 0
  alphaR^-1(MU) - alphaL^-1(MU) = 0
for x=ln(MI), y=ln(MU), rather than nesting a first-crossing search.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
GATE_PATH = HERE / "ftoe_so10_422_gate.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_422_gate_2d", GATE_PATH)
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

# Reproduce the primary-paper boundary conditions exactly.
core.MZ = 91.2
core.ALPHA1_INV_MZ = 59.0272
core.ALPHA2_INV_MZ = 29.5879
core.ALPHA3_INV_MZ = 8.4678


def residual_xy(x: float, y: float, threshold: float):
    mi, mu = math.exp(x), math.exp(y)
    if mu <= mi or mi <= core.MZ:
        raise ValueError("invalid scale ordering")
    low = core.low_energy_couplings_two_loop(mi, threshold=threshold)
    a4 = low["3"]
    aL = low["2"]
    aR = (5.0/3.0)*low["1"] - (2.0/3.0)*a4
    inv = core.evolve_two_loop((a4, aL, aR), mi, mu, core.A_422, core.BIJ_422, steps_per_log=72)
    return inv[0]-inv[1], inv[2]-inv[1], inv


def newton(seed_x: float, seed_y: float, threshold: float, max_iter: int = 32, tol: float = 2e-7):
    x, y = float(seed_x), float(seed_y)
    xmin, xmax = math.log(1e5), math.log(1e14)
    ymax = math.log(1e19)
    for _ in range(max_iter):
        if not (xmin <= x <= xmax and x + 0.05 < y <= ymax):
            return None
        try:
            f1, f2, inv = residual_xy(x, y, threshold)
        except ValueError:
            return None
        norm = max(abs(f1), abs(f2))
        if norm < tol:
            spread = max(inv)-min(inv)
            return {
                "MI_GeV": math.exp(x),
                "MU_GeV": math.exp(y),
                "log10_MI": x/math.log(10.0),
                "log10_MU": y/math.log(10.0),
                "alpha_U": 1.0/(sum(inv)/3.0),
                "inverse_couplings": {"4": inv[0], "L": inv[1], "R": inv[2]},
                "F1_4_minus_L": f1,
                "F2_R_minus_L": f2,
                "max_spread": spread,
            }
        # Central finite-difference Jacobian in logarithmic variables.
        h = 2e-4
        try:
            fxp = residual_xy(x+h, y, threshold)
            fxm = residual_xy(x-h, y, threshold)
            fyp = residual_xy(x, y+h, threshold)
            fym = residual_xy(x, y-h, threshold)
        except ValueError:
            return None
        j11 = (fxp[0]-fxm[0])/(2*h)
        j21 = (fxp[1]-fxm[1])/(2*h)
        j12 = (fyp[0]-fym[0])/(2*h)
        j22 = (fyp[1]-fym[1])/(2*h)
        det = j11*j22 - j12*j21
        if abs(det) < 1e-12:
            return None
        dx = (-f1*j22 + j12*f2)/det
        dy = (j21*f1 - j11*f2)/det
        # Damped Newton protects against jumping out of the physical domain.
        scale = max(1.0, abs(dx)/1.5, abs(dy)/1.5)
        x += dx/scale
        y += dy/scale
    return None


def solve_all(threshold: float, nx: int = 8, ny: int = 8):
    x0, x1 = math.log(1e6), math.log(1e14)
    y0, y1 = math.log(1e14), math.log(1e18)
    roots = []
    for ix in range(nx):
        x = x0 + (x1-x0)*(ix+0.5)/nx
        for iy in range(ny):
            y = y0 + (y1-y0)*(iy+0.5)/ny
            if y <= x + 0.1:
                continue
            root = newton(x, y, threshold)
            if root is None:
                continue
            if root["max_spread"] > 1e-4:
                continue
            if not any(abs(root["log10_MI"]-old["log10_MI"]) < 1e-4 and abs(root["log10_MU"]-old["log10_MU"]) < 1e-4 for old in roots):
                roots.append(root)
    roots.sort(key=lambda r: (r["MI_GeV"], r["MU_GeV"]))
    return roots


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", choices=("reference", "ftoe"), default="ftoe")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    threshold = core.MZ if args.threshold == "reference" else core.M_I_PHYS
    roots = solve_all(threshold)
    payload = {
        "schema": "FTOE-SO10-422-2D-ROOTS-v0.1",
        "mode": args.threshold,
        "threshold_GeV": threshold,
        "root_count": len(roots),
        "roots": roots,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
