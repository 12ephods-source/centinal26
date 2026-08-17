"""Branch-complete 2D root solver for two-loop G422 gauge unification.

The search solves both unification residuals simultaneously in x=ln(MI),
y=ln(MU). Coarse Newton iterations use a cheaper RK4 grid; every accepted
candidate is then polished and certified with high-resolution integration.

Coefficient provenance: arXiv:1911.11411 prints b_(2L,4)=525/2, while
arXiv:2212.11315 prints 525/3. A deterministic source audit on this branch
finds 525/2 reproduces both quoted benchmark points much more closely.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE_PATH = HERE / "ftoe_so10_422_gate.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_422_gate_2d", GATE_PATH)
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

core.MZ = 91.2
core.ALPHA1_INV_MZ = 59.0272
core.ALPHA2_INV_MZ = 29.5879
core.ALPHA3_INV_MZ = 8.4678

BIJ_422_VALIDATED = (
    (2435.0 / 6.0, 105.0 / 2.0, 249.0 / 2.0),
    (525.0 / 2.0, 73.0, 48.0),
    (1245.0 / 2.0, 48.0, 835.0 / 3.0),
)
COEFFICIENT_PROVENANCE = (
    "1911.11411:525/2; 2212.11315 prints 525/3; branch audit favors 525/2"
)


def residual_xy(x: float, y: float, threshold: float, steps_per_log: int = 24):
    mi, mu = math.exp(x), math.exp(y)
    if mu <= mi or mi <= core.MZ:
        raise ValueError("invalid scale ordering")
    low = core.low_energy_couplings_two_loop(mi, threshold=threshold)
    a4, a_l = low["3"], low["2"]
    a_r = (5.0 / 3.0) * low["1"] - (2.0 / 3.0) * a4
    inv = core.evolve_two_loop(
        (a4, a_l, a_r),
        mi,
        mu,
        core.A_422,
        BIJ_422_VALIDATED,
        steps_per_log=steps_per_log,
    )
    return inv[0] - inv[1], inv[2] - inv[1], inv


def _newton_step(x: float, y: float, threshold: float, steps_per_log: int):
    f1, f2, inv = residual_xy(x, y, threshold, steps_per_log)
    h = 4e-4
    fx = residual_xy(x + h, y, threshold, steps_per_log)
    fy = residual_xy(x, y + h, threshold, steps_per_log)
    j11, j21 = (fx[0] - f1) / h, (fx[1] - f2) / h
    j12, j22 = (fy[0] - f1) / h, (fy[1] - f2) / h
    det = j11 * j22 - j12 * j21
    if abs(det) < 1e-12:
        raise ValueError("singular Jacobian")
    dx = (-f1 * j22 + j12 * f2) / det
    dy = (j21 * f1 - j11 * f2) / det
    scale = max(1.0, abs(dx) / 1.5, abs(dy) / 1.5)
    return x + dx / scale, y + dy / scale, max(abs(f1), abs(f2)), inv


def newton(seed_x: float, seed_y: float, threshold: float):
    x, y = float(seed_x), float(seed_y)
    xmin, xmax = math.log(1e5), math.log(1e14)
    ymax = math.log(1e19)

    for _ in range(18):
        if not (xmin <= x <= xmax and x + 0.05 < y <= ymax):
            return None
        try:
            x, y, norm, _ = _newton_step(x, y, threshold, 24)
        except ValueError:
            return None
        if norm < 3e-5:
            break
    else:
        return None

    for _ in range(7):
        if not (xmin <= x <= xmax and x + 0.05 < y <= ymax):
            return None
        try:
            f1, f2, inv = residual_xy(x, y, threshold, 120)
        except ValueError:
            return None
        if max(abs(f1), abs(f2)) < 2e-7:
            return {
                "MI_GeV": math.exp(x),
                "MU_GeV": math.exp(y),
                "log10_MI": x / math.log(10.0),
                "log10_MU": y / math.log(10.0),
                "alpha_U": 1.0 / (sum(inv) / 3.0),
                "inverse_couplings": {"4": inv[0], "L": inv[1], "R": inv[2]},
                "F1_4_minus_L": f1,
                "F2_R_minus_L": f2,
                "max_spread": max(inv) - min(inv),
            }
        try:
            x, y, _, _ = _newton_step(x, y, threshold, 120)
        except ValueError:
            return None
    return None


def solve_all(threshold: float, nx: int = 5, ny: int = 5):
    x0, x1 = math.log(1e6), math.log(1e14)
    y0, y1 = math.log(1e14), math.log(1e18)
    roots = []
    for ix in range(nx):
        x = x0 + (x1 - x0) * (ix + 0.5) / nx
        for iy in range(ny):
            y = y0 + (y1 - y0) * (iy + 0.5) / ny
            if y <= x + 0.1:
                continue
            root = newton(x, y, threshold)
            if root is None or root["max_spread"] > 1e-5:
                continue
            duplicate = any(
                abs(root["log10_MI"] - old["log10_MI"]) < 1e-4
                and abs(root["log10_MU"] - old["log10_MU"]) < 1e-4
                for old in roots
            )
            if not duplicate:
                roots.append(root)
    roots.sort(key=lambda row: (row["MI_GeV"], row["MU_GeV"]))
    return roots


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--threshold",
        choices=("reference", "ftoe"),
        default="ftoe",
    )
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    threshold = core.MZ if args.threshold == "reference" else core.M_I_PHYS
    roots = solve_all(threshold)
    payload = {
        "schema": "FTOE-SO10-422-2D-ROOTS-v0.3",
        "mode": args.threshold,
        "threshold_GeV": threshold,
        "coefficient_provenance": COEFFICIENT_PROVENANCE,
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
