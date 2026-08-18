"""Adversarial threshold/alpha_s stress harness for the FToE SO(10)->G422 branch.

This attack does not fabricate a proton lifetime before the model-specific
heavy spectrum and decay normalization are frozen. Instead it re-solves the
validated gauge branch over a pre-declared input grid and maps the exact
experimental exclusion boundary onto the unresolved dimension-6 decay
prefactor K in

    Gamma(p -> e+ pi0) = K * alpha_U^2 / M_X^4,

with M_X = r_X * M_U. K has units GeV^5 and intentionally absorbs the
operator normalization, group/flavor factors, short/long-distance running and
hadronic matrix elements that must later be derived from the same frozen
spectrum. A point is excluded only after an independently frozen model value
of K is supplied; this script never tunes K to force survival.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE_PATH = HERE / "ftoe_so10_422_gate.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_422_gate_stress", CORE_PATH)
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

HBAR_GEV_S = 6.582119569e-25
SECONDS_PER_YEAR = 365.25 * 24.0 * 3600.0
SK_EPI0_LIMIT_YR = 2.4e34
SK_EPI0_SOURCE = "Super-Kamiokande, Phys. Rev. D 102, 112011 (2020), arXiv:2010.16098"
REFERENCE_MZ_GEV = 91.2
REFERENCE_ALPHA1_INV = 59.0272
REFERENCE_ALPHA2_INV = 29.5879
REFERENCE_ALPHA3_INV = 8.4678
REFERENCE_ALPHA_S = 1.0 / REFERENCE_ALPHA3_INV
DEFAULT_ALPHA_S_VALUES = (0.1170, REFERENCE_ALPHA_S, 0.1192)
DEFAULT_THRESHOLD_FACTORS = (0.5, 1.0, 2.0)

BIJ_422_VALIDATED = (
    (2435.0 / 6.0, 105.0 / 2.0, 249.0 / 2.0),
    (525.0 / 2.0, 73.0, 48.0),
    (1245.0 / 2.0, 48.0, 835.0 / 3.0),
)
COEFFICIENT_PROVENANCE = (
    "1911.11411:525/2; 2212.11315 prints 525/3; branch source audit and "
    "validated 2D solver use 525/2"
)


def decay_prefactor_limit_geV5(
    mu_u: float,
    alpha_u: float,
    lifetime_limit_yr: float = SK_EPI0_LIMIT_YR,
    mx_over_mu: float = 1.0,
) -> float:
    if min(mu_u, alpha_u, lifetime_limit_yr, mx_over_mu) <= 0.0:
        raise ValueError("all decay-boundary inputs must be positive")
    mx = mx_over_mu * mu_u
    gamma_limit_gev = HBAR_GEV_S / (lifetime_limit_yr * SECONDS_PER_YEAR)
    return gamma_limit_gev * mx**4 / alpha_u**2


def parse_csv_floats(text: str) -> tuple[float, ...]:
    values = tuple(float(item.strip()) for item in text.split(",") if item.strip())
    if not values or any(value <= 0.0 for value in values):
        raise ValueError("grid values must be positive")
    return values


def _solve_point(alpha_s: float, threshold_gev: float):
    core.MZ = REFERENCE_MZ_GEV
    core.ALPHA1_INV_MZ = REFERENCE_ALPHA1_INV
    core.ALPHA2_INV_MZ = REFERENCE_ALPHA2_INV
    core.ALPHA3_INV_MZ = 1.0 / alpha_s
    core.BIJ_422 = BIJ_422_VALIDATED
    return core.solve_two_loop_422(threshold=threshold_gev)


def run_sweep(
    alpha_s_values: tuple[float, ...] = DEFAULT_ALPHA_S_VALUES,
    threshold_factors: tuple[float, ...] = DEFAULT_THRESHOLD_FACTORS,
    mx_over_mu: float = 1.0,
    lifetime_limit_yr: float = SK_EPI0_LIMIT_YR,
    solver=None,
) -> dict:
    solver = solver or _solve_point
    rows = []
    failures = []
    for alpha_s in alpha_s_values:
        for factor in threshold_factors:
            threshold = core.M_I_PHYS * factor
            try:
                mi, mu, alpha_u, inverse, spread = solver(alpha_s, threshold)
            except Exception as exc:  # noqa: BLE001 - adversarial grid must preserve unexpected solver failures
                failures.append(
                    {
                        "alpha_s_MZ": alpha_s,
                        "threshold_factor": factor,
                        "threshold_GeV": threshold,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            reduced = mu**4 / alpha_u**2
            rows.append(
                {
                    "alpha_s_MZ": alpha_s,
                    "threshold_factor": factor,
                    "threshold_GeV": threshold,
                    "MI_GeV": mi,
                    "MU_GeV": mu,
                    "alpha_U": alpha_u,
                    "inverse_couplings": inverse,
                    "max_spread": spread,
                    "proton_decay_reduced_scale_GeV4": reduced,
                    "max_decay_prefactor_GeV5_at_limit": decay_prefactor_limit_geV5(
                        mu,
                        alpha_u,
                        lifetime_limit_yr=lifetime_limit_yr,
                        mx_over_mu=mx_over_mu,
                    ),
                }
            )

    baseline = None
    if rows:
        baseline = min(
            rows,
            key=lambda row: abs(row["alpha_s_MZ"] - REFERENCE_ALPHA_S)
            + abs(math.log(row["threshold_factor"])),
        )
        base_reduced = baseline["proton_decay_reduced_scale_GeV4"]
        for row in rows:
            row["reduced_scale_ratio_to_baseline"] = (
                row["proton_decay_reduced_scale_GeV4"] / base_reduced
            )

    return {
        "schema": "FTOE-SO10-THRESHOLD-STRESS-v0.2",
        "attack_vector": "THRESHOLD_MATCHING_STRESS_TEST",
        "coefficient_provenance": COEFFICIENT_PROVENANCE,
        "input_contract": {
            "alpha_s_values": list(alpha_s_values),
            "alpha_s_grid_semantics": "predeclared adversarial envelope around the branch reference input; not a claim of a new world average",
            "reference_alpha_s_MZ": REFERENCE_ALPHA_S,
            "threshold_factors": list(threshold_factors),
            "nominal_informational_threshold_GeV": core.M_I_PHYS,
            "mx_over_mu": mx_over_mu,
            "partial_lifetime_limit_yr": lifetime_limit_yr,
            "partial_lifetime_limit_source": SK_EPI0_SOURCE,
        },
        "decay_boundary_convention": {
            "equation": "Gamma = K * alpha_U^2 / M_X^4",
            "M_X_relation": "M_X = mx_over_mu * M_U",
            "K_units": "GeV^5",
            "interpretation": "K is unresolved until derived from the frozen heavy spectrum, operator normalization, flavor structure, RG factors and hadronic matrix elements.",
        },
        "root_selection": "validated principal gauge root with explicitly aligned 525/2 G422 coefficient; exhaustive multi-root enumeration remains a separate mandatory scientific gate",
        "point_count": len(rows),
        "failure_count": len(failures),
        "baseline": baseline,
        "points": rows,
        "failures": failures,
        "gate": "PASS_STRESS_EXECUTION" if rows and not failures else "FAIL_STRESS_EXECUTION",
        "scientific_status": "REVIEW",
        "proton_decay_status": "BOUNDARY_MAPPED_PREFACTOR_UNRESOLVED",
        "stop_condition": "Do not classify any point excluded or allowed until K and M_X/M_U are frozen independently from the same heavy spectrum.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--alpha-s",
        default=",".join(f"{x:.12g}" for x in DEFAULT_ALPHA_S_VALUES),
        help="comma-separated alpha_s(MZ) attack grid",
    )
    parser.add_argument(
        "--threshold-factors",
        default=",".join(f"{x:.12g}" for x in DEFAULT_THRESHOLD_FACTORS),
        help="comma-separated factors multiplying the nominal informational threshold",
    )
    parser.add_argument("--mx-over-mu", type=float, default=1.0)
    parser.add_argument("--lifetime-limit-yr", type=float, default=SK_EPI0_LIMIT_YR)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = run_sweep(
        alpha_s_values=parse_csv_floats(args.alpha_s),
        threshold_factors=parse_csv_floats(args.threshold_factors),
        mx_over_mu=args.mx_over_mu,
        lifetime_limit_yr=args.lifetime_limit_yr,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    if result["gate"] != "PASS_STRESS_EXECUTION":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
