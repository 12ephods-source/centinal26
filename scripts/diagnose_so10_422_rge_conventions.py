"""Cross-check published G422 two-loop coefficient sets against benchmarks.

Primary-source discrepancy under test:
- Meloni/Ohlsson/Pernow (arXiv:1911.11411) prints b_L4 = 525/2.
- Djouadi/Fonseca/Ouyang/Raidal (arXiv:2212.11315) prints b_L4 = 525/3.

The script evaluates each matrix at both publications' quoted no-threshold
(two-loop) scale points. It does not select a matrix by desired fit; it reports
all residuals for provenance/audit.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE_PATH = HERE / "ftoe_so10_422_gate.py"
spec = importlib.util.spec_from_file_location("ftoe_diag_core", CORE_PATH)
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

LATER_BC = {"MZ": 91.2, "a1": 59.0272, "a2": 29.5879, "a3": 8.4678}

B422_2023_PRINTED = (
    (2435.0 / 6.0, 105.0 / 2.0, 249.0 / 2.0),
    (525.0 / 3.0, 73.0, 48.0),
    (1245.0 / 2.0, 48.0, 835.0 / 3.0),
)
B422_2020_PRINTED = (
    (2435.0 / 6.0, 105.0 / 2.0, 249.0 / 2.0),
    (525.0 / 2.0, 73.0, 48.0),
    (1245.0 / 2.0, 48.0, 835.0 / 3.0),
)
A422 = (-7.0 / 3.0, 2.0, 28.0 / 3.0)

POINTS = {
    "2023_table3_2hdm": {"log_mi": 10.03, "log_mu": 16.19, "threshold": 91.2},
    "2020_sm_result": {"mi": 2.64e9, "mu": 3.72e16, "threshold": float("inf")},
}


def set_bc() -> None:
    core.MZ = LATER_BC["MZ"]
    core.ALPHA1_INV_MZ = LATER_BC["a1"]
    core.ALPHA2_INV_MZ = LATER_BC["a2"]
    core.ALPHA3_INV_MZ = LATER_BC["a3"]


def residual_at(mi, mu, threshold, matrix):
    low = core.low_energy_couplings_two_loop(mi, threshold=threshold)
    a4 = low["3"]
    a_l = low["2"]
    a_r = (5.0 / 3.0) * low["1"] - (2.0 / 3.0) * a4
    inv = core.evolve_two_loop(
        (a4, a_l, a_r),
        mi,
        mu,
        A422,
        matrix,
        steps_per_log=220,
    )
    out = {"4": inv[0], "L": inv[1], "R": inv[2]}
    return {
        "spread": max(inv) - min(inv),
        "4_minus_L": inv[0] - inv[1],
        "R_minus_L": inv[2] - inv[1],
        "inverse": out,
    }


def main() -> None:
    set_bc()
    matrices = {
        "2020_printed_525_over_2": B422_2020_PRINTED,
        "2023_printed_525_over_3": B422_2023_PRINTED,
    }
    results = {}
    for point_name, point in POINTS.items():
        if "mi" in point:
            mi = point["mi"]
            mu = point["mu"]
        else:
            mi = 10.0 ** point["log_mi"]
            mu = 10.0 ** point["log_mu"]
        results[point_name] = {
            matrix_name: residual_at(mi, mu, point["threshold"], matrix)
            for matrix_name, matrix in matrices.items()
        }
    print(
        json.dumps(
            {
                "schema": "SO10-422-COEFFICIENT-SOURCE-AUDIT-v0.3",
                "note": (
                    "reports both primary-source coefficient sets; "
                    "does not promote either by proximity"
                ),
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
