"""Postprocess FToE-specific two-loop G422 roots without retuning.

For every certified FToE threshold root this script computes the hierarchy scan,
Lambda_X/beta tail, and a proton-lifetime scale proxy. The proton quantity is
not a prediction because the frozen heavy gauge spectrum and flavor/hadronic
inputs remain underived.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOTS_PATH = HERE / "ftoe_so10_422_2d_roots.py"
spec = importlib.util.spec_from_file_location("ftoe_roots_post", ROOTS_PATH)
assert spec and spec.loader
rootsmod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rootsmod
spec.loader.exec_module(rootsmod)

MP = 1.22089e19
MU_I = 9.54e3
XI_I = 1.0 / 6.0
CURVATURE_COEFF = 7.31


def hierarchy_scan(mu_u: float):
    target = (MU_I / mu_u) ** 2
    ratio = mu_u / MP
    rows = []
    for power in range(1, 13):
        coeff = target / ratio**power
        rows.append({"n": power, "coefficient_times_clebsch": coeff})
    best = min(
        rows,
        key=lambda row: abs(math.log10(row["coefficient_times_clebsch"])),
    )
    return target, ratio, rows, best


def beta_tail():
    coeff = CURVATURE_COEFF * XI_I / 2.0
    lambda_x = (MU_I * MU_I * MP * MP / coeff) ** 0.25
    return lambda_x, (lambda_x / MP) ** 2


def proton_scale_proxy(mu_u: float, alpha_u: float):
    return 7.5e35 * (mu_u / 1.0e16) ** 4 * (0.03 / alpha_u) ** 2


def main() -> None:
    rootsmod.core.MZ = 91.2
    rootsmod.core.ALPHA1_INV_MZ = 59.0272
    rootsmod.core.ALPHA2_INV_MZ = 29.5879
    rootsmod.core.ALPHA3_INV_MZ = 8.4678

    roots = rootsmod.solve_all(threshold=rootsmod.core.M_I_PHYS, nx=3, ny=3)
    lambda_x, beta = beta_tail()
    processed = []
    for root in roots:
        target, ratio, scan, best = hierarchy_scan(root["MU_GeV"])
        processed.append(
            {
                "root": root,
                "hierarchy_target_muI2_over_MU2": target,
                "MU_over_MP": ratio,
                "hierarchy_scan": scan,
                "preferred_integer_power": best["n"],
                "preferred_coefficient_times_clebsch": best[
                    "coefficient_times_clebsch"
                ],
                "proton_lifetime_scale_proxy_years": proton_scale_proxy(
                    root["MU_GeV"],
                    root["alpha_U"],
                ),
                "proton_proxy_status": "PROXY_ONLY_NOT_PREDICTION",
            }
        )

    hierarchy_gate = (
        "PASS"
        if roots
        and any(
            0.1 <= row["preferred_coefficient_times_clebsch"] <= 10
            for row in processed
        )
        else "REVIEW"
    )
    payload = {
        "schema": "FTOE-SO10-422-POSTPROCESS-v0.1",
        "coefficient_provenance": rootsmod.COEFFICIENT_PROVENANCE,
        "informational_mass_parameter_GeV": MU_I,
        "informational_physical_mass_GeV": math.sqrt(2.0) * MU_I,
        "Lambda_X_GeV": lambda_x,
        "beta_conditional_on_muI": beta,
        "roots": processed,
        "gates": {
            "gauge_only_two_loop_422": "PASS" if roots else "FAIL",
            "hierarchy_order_one_candidate": hierarchy_gate,
            "explicit_SO10_operator_Clebsch": "NOT_TESTED",
            "lower_dimension_operator_exclusion": "NOT_TESTED",
            "heavy_threshold_spectrum": "NOT_TESTED",
            "proton_decay_frozen_spectrum": "NOT_TESTED",
        },
        "scientific_status": "REVIEW",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
