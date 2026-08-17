#!/usr/bin/env python3
"""Diagnose convention-level causes of the 2212.11315 G422 benchmark mismatch.

This script does not alter the physics model and does not choose a convention to
fit the published answer.  It evaluates the published Table-2 point under every
permutation of the printed G422 coefficient ordering, and under the printed
matrix versus its transpose, then reports residuals.  The intended use is to
locate a convention/transcription/source inconsistency before any FToE-specific
result is trusted.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
CORE_PATH = HERE / "ftoe_so10_422_gate.py"
spec = importlib.util.spec_from_file_location("ftoe_diag_core", CORE_PATH)
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

core.MZ = 91.2
core.ALPHA1_INV_MZ = 59.0272
core.ALPHA2_INV_MZ = 29.5879
core.ALPHA3_INV_MZ = 8.4678

TABLE2_LOG_MI = 10.133
TABLE2_LOG_MU = 16.346
TABLE3_LOG_MI = 10.03
TABLE3_LOG_MU = 16.19


def transpose(m):
    return tuple(tuple(m[j][i] for j in range(len(m))) for i in range(len(m)))


def residual_at(log_mi, log_mu, labels, matrix):
    mi, mu = 10.0**log_mi, 10.0**log_mu
    low = core.low_energy_couplings_two_loop(mi, threshold=core.MZ)
    physical = {
        "4": low["3"],
        "L": low["2"],
        "R": (5.0/3.0)*low["1"] - (2.0/3.0)*low["3"],
    }
    a_phys = {"4": -7.0/3.0, "L": 2.0, "R": 28.0/3.0}
    # Printed table coordinates are interpreted according to `labels`.
    inv0 = tuple(physical[label] for label in labels)
    avec = tuple(a_phys[label] for label in labels)
    inv = core.evolve_two_loop(inv0, mi, mu, avec, matrix, steps_per_log=180)
    out = {label: inv[i] for i, label in enumerate(labels)}
    return {
        "spread": max(out.values())-min(out.values()),
        "4_minus_L": out["4"]-out["L"],
        "R_minus_L": out["R"]-out["L"],
        "inverse": out,
    }


def main():
    rows = []
    printed = core.BIJ_422
    for matrix_name, matrix in (("printed", printed), ("transpose", transpose(printed))):
        for labels in itertools.permutations(("4", "L", "R")):
            r2 = residual_at(TABLE2_LOG_MI, TABLE2_LOG_MU, labels, matrix)
            r3 = residual_at(TABLE3_LOG_MI, TABLE3_LOG_MU, labels, matrix)
            rows.append({
                "matrix": matrix_name,
                "printed_index_labels": labels,
                "table2": r2,
                "table3": r3,
            })
    rows.sort(key=lambda r: r["table2"]["spread"])
    print(json.dumps({
        "schema": "SO10-422-RGE-CONVENTION-DIAGNOSTIC-v0.1",
        "note": "diagnostic only; no convention is promoted by proximity to target",
        "rows": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
