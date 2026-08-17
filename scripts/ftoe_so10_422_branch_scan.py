#!/usr/bin/env python3
"""Enumerate all gauge-only two-loop G422 shooting branches.

This companion avoids selecting the first residual zero.  Every sign-change root
in the requested MI interval is refined independently and retained.  Scientific
selection among branches must be made by explicit external gates, never by
choosing the root closest to a desired answer.
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
spec = importlib.util.spec_from_file_location("ftoe_so10_422_gate", GATE_PATH)
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def sign_change_brackets(fn, lo: float, hi: float, samples: int = 320):
    if lo <= 0 or hi <= lo:
        raise ValueError("invalid interval")
    l0, l1 = math.log(lo), math.log(hi)
    xs = [math.exp(l0 + (l1-l0)*i/samples) for i in range(samples+1)]
    vals = []
    for x in xs:
        try:
            vals.append(fn(x))
        except ValueError:
            vals.append(None)
    brackets = []
    for x0, x1, f0, f1 in zip(xs, xs[1:], vals, vals[1:]):
        if f0 is None or f1 is None:
            continue
        if f0 == 0.0:
            brackets.append((x0, x0))
        elif f0*f1 < 0.0:
            brackets.append((x0, x1))
    if vals[-1] == 0.0:
        brackets.append((xs[-1], xs[-1]))
    return brackets


def solve_branches(threshold: float, lo: float = 1e6, hi: float = 1e14, samples: int = 320):
    fn = lambda x: core.two_loop_mi_residual(x, threshold=threshold)
    rows = []
    for blo, bhi in sign_change_brackets(fn, lo, hi, samples=samples):
        mi = blo if blo == bhi else core.bisect_log_root(fn, blo, bhi, iterations=90, tol=2e-6)
        mu, residual, inverse = core.shoot_422_two_loop(mi, threshold=threshold, step_log=0.0015)
        spread = max(inverse.values()) - min(inverse.values())
        alpha_u = 1.0/(sum(inverse.values())/3.0)
        row = {
            "MI_GeV": mi,
            "MU_GeV": mu,
            "log10_MI": math.log10(mi),
            "log10_MU": math.log10(mu),
            "alpha_U": alpha_u,
            "R_minus_4_residual": residual,
            "inverse_couplings": inverse,
            "max_spread": spread,
        }
        if not any(abs(math.log10(row["MI_GeV"]/old["MI_GeV"])) < 1e-5 for old in rows):
            rows.append(row)
    rows.sort(key=lambda row: row["MI_GeV"])
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", choices=("reference", "ftoe"), default="ftoe")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    # Paper Eq. (35) boundary conditions are used for both regression and the
    # FToE threshold comparison so that the threshold is the controlled change.
    core.MZ = 91.2
    core.ALPHA1_INV_MZ = 59.0272
    core.ALPHA2_INV_MZ = 29.5879
    core.ALPHA3_INV_MZ = 8.4678
    threshold = core.MZ if args.threshold == "reference" else core.M_I_PHYS
    rows = solve_branches(threshold)
    payload = {
        "schema": "FTOE-SO10-422-BRANCH-SCAN-v0.1",
        "mode": args.threshold,
        "threshold_GeV": threshold,
        "branch_count": len(rows),
        "branches": rows,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
