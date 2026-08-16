#!/usr/bin/env python3
"""Discretized de Sitter diamond -> modular/cocycle -> relational-map harness.

This is the first geometry-bearing extension stacked on the validated finite Type-I
KMS/modular/cocycle baseline.  It deliberately remains a regulated finite surrogate:
no continuum Type-II/III classification, gravitational canonical-energy identity,
or Einstein reconstruction is inferred from these calculations.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
CANDIDATES = HERE.parent
BETA = 2.0 * np.pi
L_DS = 1.0
X_MAX = 4.0
N_SITE_SCAN = (31, 63, 127, 255)
MODE_COUNT = 3
T_RATIOS = (1.0, 2.0, 4.0, 8.0)
ETA_TARGET = 0.0625
Q_MAX = 8.0
SIGMA_RATIO = 1.0 / 16.0
MODULAR_PARAMETER = 0.25
N_CUT = 5
THRESH = {
    "metric_identity": 1.0e-13,
    "matrix_spectrum": 1.0e-11,
    "final_mode_relative_error": 1.0e-4,
    "convergence_ratio": 3.5,
    "kms": 1.0e-10,
    "cocycle": 1.0e-10,
    "clock_closure": 1.0e-12,
    "clock_min_eigenvalue": -1.0e-12,
    "relational_continuum_relative_error": 1.0e-2,
    "retention_minimum": 1.0e-8,
}


def load_parent_module(name: str, relative_path: str):
    """Load an already-validated parent harness without copying its implementation."""
    path = CANDIDATES / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load parent harness: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLOCK = load_parent_module(
    "clock_regulator_scan_parent",
    "clock-regulator-harness/clock_regulator_scan.py",
)
KMS = load_parent_module(
    "kms_modular_cocycle_scan_parent",
    "kms-modular-cocycle-harness/kms_modular_cocycle_scan.py",
)


def continuum_frequencies(
    *, x_max: float = X_MAX, mode_count: int = MODE_COUNT
) -> np.ndarray:
    """Dirichlet frequencies for the conformally flat dS2 static-patch interval."""
    if x_max <= 0.0 or mode_count < 1:
        raise ValueError("x_max and mode_count must be positive")
    k = np.arange(1, mode_count + 1, dtype=float)
    return k * np.pi / (2.0 * x_max)


def lattice_frequencies(
    n_sites: int, *, x_max: float = X_MAX, mode_count: int = MODE_COUNT
) -> np.ndarray:
    """Exact eigenfrequencies of the second-difference Dirichlet Laplacian."""
    if n_sites < mode_count or n_sites < 2:
        raise ValueError("n_sites must be >= mode_count and >=2")
    h = 2.0 * x_max / (n_sites + 1)
    k = np.arange(1, mode_count + 1, dtype=float)
    return (2.0 / h) * np.sin(k * np.pi / (2.0 * (n_sites + 1)))


def laplacian_matrix(n_sites: int, *, x_max: float = X_MAX) -> np.ndarray:
    """Return the positive operator -d^2/dx^2 on the stretched static patch."""
    if n_sites < 2:
        raise ValueError("n_sites must be >=2")
    h = 2.0 * x_max / (n_sites + 1)
    matrix = np.diag(np.full(n_sites, 2.0))
    matrix += np.diag(np.full(n_sites - 1, -1.0), 1)
    matrix += np.diag(np.full(n_sites - 1, -1.0), -1)
    return matrix / h**2


def geometry_metrics() -> dict[str, Any]:
    """Validate the dS2 static-patch conformal coordinate and lattice spectrum."""
    xs = np.linspace(-X_MAX, X_MAX, 257)
    r = L_DS * np.tanh(xs / L_DS)
    sech2 = 1.0 / np.cosh(xs / L_DS) ** 2
    lapse = 1.0 - (r / L_DS) ** 2
    dr_dx = sech2
    metric_identity_residual = float(
        max(
            np.max(np.abs(lapse - sech2)),
            np.max(np.abs(dr_dx - sech2)),
        )
    )

    n_matrix = N_SITE_SCAN[0]
    evals = np.linalg.eigvalsh(laplacian_matrix(n_matrix))
    matrix_freqs = np.sqrt(np.maximum(evals[:MODE_COUNT], 0.0))
    formula_freqs = lattice_frequencies(n_matrix)
    matrix_spectrum_residual = float(
        np.max(np.abs(matrix_freqs - formula_freqs) / formula_freqs)
    )

    continuum = continuum_frequencies()
    rows: list[dict[str, Any]] = []
    errors: list[np.ndarray] = []
    for n_sites in N_SITE_SCAN:
        freqs = lattice_frequencies(n_sites)
        rel = np.abs(freqs - continuum) / continuum
        errors.append(rel)
        rows.append(
            {
                "n_sites": n_sites,
                "delta_x": 2.0 * X_MAX / (n_sites + 1),
                "frequencies": freqs.tolist(),
                "continuum_frequencies": continuum.tolist(),
                "relative_errors": rel.tolist(),
                "max_relative_error": float(np.max(rel)),
            }
        )

    ratios = []
    for earlier, later in zip(errors[:-1], errors[1:], strict=True):
        ratios.append(float(np.min(earlier / later)))

    return {
        "dimension": "1+1",
        "radius_L": L_DS,
        "static_metric": "ds^2=sech^2(x/L)(-dt^2+dx^2), r=L*tanh(x/L)",
        "field": "massless conformal scalar; xi_2=0",
        "boundary_condition": "Dirichlet at stretched horizons x=+/-X_MAX",
        "x_max": X_MAX,
        "metric_coordinate_identity_residual": metric_identity_residual,
        "matrix_vs_closed_form_spectrum_max_relative_residual": matrix_spectrum_residual,
        "scan": rows,
        "minimum_successive_error_reduction_ratio": min(ratios),
        "final_max_mode_relative_error": float(np.max(errors[-1])),
    }


def geometry_kms_cocycle_metrics() -> dict[str, Any]:
    """Feed a geometry-derived normal mode into the validated finite Type-I algebra."""
    omega = float(lattice_frequencies(N_SITE_SCAN[-1], mode_count=1)[0])
    a, number, h = KMS.oscillator(N_CUT, omega)
    rho0 = KMS.thermal(h, BETA)
    x_op = (a + a.conj().T) / np.sqrt(2.0)
    b_op = number + 0.13 * x_op

    flow_residuals = []
    for s in (-0.25, -0.125, 0.125, 0.25):
        flow_residuals.append(
            KMS.nr(
                KMS.sigma(rho0, s, x_op),
                KMS.alpha(h, -BETA * s, x_op),
            )
        )

    sig_i_x = np.linalg.inv(rho0) @ x_op @ rho0
    left = np.trace(rho0 @ sig_i_x @ b_op)
    right = np.trace(rho0 @ b_op @ x_op)
    kms_residual = float(abs(left - right) / max(1.0, abs(left), abs(right)))

    displacement = KMS.displace(N_CUT, 0.10 * (0.31 + 0.17j))
    rho1 = displacement @ rho0 @ displacement.conj().T
    cocycle_residuals = []
    intertwining_residuals = []
    for s in (-0.25, -0.125, 0.125, 0.25):
        u_s = KMS.cocycle(rho1, rho0, s)
        cocycle_residuals.append(KMS.nr(u_s.conj().T @ u_s, np.eye(N_CUT)))
        intertwining_residuals.append(
            KMS.nr(
                KMS.sigma(rho1, s, x_op),
                u_s @ KMS.sigma(rho0, s, x_op) @ u_s.conj().T,
            )
        )
    for s, t in ((0.25, -0.125), (-0.125, 0.25), (0.125, 0.125)):
        cocycle_residuals.append(
            KMS.nr(
                KMS.cocycle(rho1, rho0, s + t),
                KMS.cocycle(rho1, rho0, s)
                @ KMS.sigma(rho0, s, KMS.cocycle(rho1, rho0, t)),
            )
        )

    return {
        "n_cut": N_CUT,
        "geometry_mode_omega": omega,
        "beta_dS": float(BETA),
        "rho0_min_eigenvalue": float(np.min(np.linalg.eigvalsh(rho0))),
        "reference_modular_to_static_flow_max_residual": max(flow_residuals),
        "kms_boundary_residual": kms_residual,
        "cocycle_and_unitarity_max_residual": max(cocycle_residuals),
        "cocycle_modular_intertwining_max_residual": max(intertwining_residuals),
    }


def relational_embedding_metrics() -> dict[str, Any]:
    """Evaluate the parent Gaussian group average as a regulated j_tau surrogate."""
    frequencies = tuple(float(x) for x in lattice_frequencies(N_SITE_SCAN[-1]))
    config = CLOCK.HarnessConfig(
        n_cut=N_CUT,
        beta=BETA,
        q_max=Q_MAX,
        sigma_ratio=SIGMA_RATIO,
        modular_parameter=MODULAR_PARAMETER,
    )
    scans: dict[str, Any] = {}
    final_rows = []
    monotonic_constraint = True
    monotonic_intertwining = True

    for mode_index, omega in enumerate(frequencies, start=1):
        rows = []
        for t_ratio in T_RATIOS:
            width = t_ratio * BETA
            n_intervals = CLOCK.select_resolved_intervals(
                q_max=Q_MAX,
                averaging_width=width,
                eta_target=ETA_TARGET,
                frequencies=frequencies,
            )
            row = CLOCK.relational_metrics(
                config=config,
                omega=omega,
                t_ratio=t_ratio,
                n_intervals=n_intervals,
            )
            row["T_over_beta"] = t_ratio
            rows.append(row)

        r_c = [float(row["R_C_over_omega"]) for row in rows]
        r_int = [float(row["R_int_corrected"]) for row in rows]
        monotonic_constraint &= all(a > b for a, b in zip(r_c[:-1], r_c[1:], strict=True))
        monotonic_intertwining &= all(
            a > b for a, b in zip(r_int[:-1], r_int[1:], strict=True)
        )
        final_rows.append(rows[-1])
        scans[f"mode_{mode_index}"] = {
            "omega": omega,
            "scan": rows,
        }

    final_delta_q = float(final_rows[0]["delta_q"])
    povm = CLOCK.time_povm_metrics(
        q_max=Q_MAX,
        delta_q=final_delta_q,
        sigma_tau=SIGMA_RATIO * BETA,
    )
    return {
        "map_definition": (
            "j_tau,T^(N)(A) := Gaussian group average of A_L tensor E_tau "
            "under C=L_matter+H_obs, using the validated clock-regulator kernel"
        ),
        "is_exact_star_homomorphism": False,
        "is_claimed_continuum_embedding": False,
        "clock_target": "H_obs=q>=0 with smeared time POVM effect",
        "eta_target": ETA_TARGET,
        "T_over_beta_scan": list(T_RATIOS),
        "modes": scans,
        "constraint_residual_strictly_decreases_with_T": monotonic_constraint,
        "intertwining_residual_strictly_decreases_with_T": monotonic_intertwining,
        "final_max_R_C_continuum_relative_error": max(
            float(row["R_C_relative_error"]) for row in final_rows
        ),
        "final_max_R_int_continuum_relative_error": max(
            float(row["R_int_relative_error"]) for row in final_rows
        ),
        "final_min_observable_retention": min(
            float(row["observable_retention"]) for row in final_rows
        ),
        "any_exact_lattice_resonance": any(
            bool(row["exact_lattice_resonance"])
            for mode in scans.values()
            for row in mode["scan"]
        ),
        "clock_povm": povm,
    }


def source_hashes() -> dict[str, str]:
    paths = {
        "this_source": Path(__file__).resolve(),
        "clock_parent": CANDIDATES / "clock-regulator-harness/clock_regulator_scan.py",
        "kms_parent": CANDIDATES
        / "kms-modular-cocycle-harness/kms_modular_cocycle_scan.py",
    }
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths.items()
    }


def evaluate_gates(
    geometry: dict[str, Any],
    kms: dict[str, Any],
    relational: dict[str, Any],
) -> dict[str, bool]:
    povm = relational["clock_povm"]
    return {
        "GEO1_static_patch_coordinate_identity": geometry[
            "metric_coordinate_identity_residual"
        ]
        <= THRESH["metric_identity"],
        "GEO2_lattice_spectrum_implementation": geometry[
            "matrix_vs_closed_form_spectrum_max_relative_residual"
        ]
        <= THRESH["matrix_spectrum"],
        "GEO3_second_order_mode_convergence": geometry[
            "final_max_mode_relative_error"
        ]
        <= THRESH["final_mode_relative_error"]
        and geometry["minimum_successive_error_reduction_ratio"]
        >= THRESH["convergence_ratio"],
        "ALG1_geometry_mode_KMS": kms["kms_boundary_residual"] <= THRESH["kms"]
        and kms["reference_modular_to_static_flow_max_residual"] <= THRESH["kms"],
        "ALG2_geometry_mode_cocycle": kms["cocycle_and_unitarity_max_residual"]
        <= THRESH["cocycle"]
        and kms["cocycle_modular_intertwining_max_residual"] <= THRESH["cocycle"],
        "REL1_constraint_suppression": relational[
            "constraint_residual_strictly_decreases_with_T"
        ]
        and relational["final_max_R_C_continuum_relative_error"]
        <= THRESH["relational_continuum_relative_error"],
        "REL2_modular_clock_intertwining": relational[
            "intertwining_residual_strictly_decreases_with_T"
        ]
        and relational["final_max_R_int_continuum_relative_error"]
        <= THRESH["relational_continuum_relative_error"],
        "REL3_clock_POVM": float(povm["R_POVM"]) <= THRESH["clock_closure"]
        and float(povm["lambda_min_E"]) >= THRESH["clock_min_eigenvalue"],
        "REL4_nontrivial_retained_observable": relational[
            "final_min_observable_retention"
        ]
        >= THRESH["retention_minimum"]
        and not relational["any_exact_lattice_resonance"],
    }


def run() -> dict[str, Any]:
    geometry = geometry_metrics()
    kms = geometry_kms_cocycle_metrics()
    relational = relational_embedding_metrics()
    gates = evaluate_gates(geometry, kms, relational)
    passed = all(gates.values())
    config = {
        "beta_dS": float(BETA),
        "L_dS": L_DS,
        "x_max": X_MAX,
        "n_site_scan": list(N_SITE_SCAN),
        "mode_count": MODE_COUNT,
        "n_cut": N_CUT,
        "T_over_beta_scan": list(T_RATIOS),
        "eta_target": ETA_TARGET,
        "q_max": Q_MAX,
        "sigma_tau_over_beta": SIGMA_RATIO,
        "modular_parameter": MODULAR_PARAMETER,
        "thresholds": THRESH,
    }
    config_hash = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "status": (
            "PASS_DS2_DIAMOND_REGULATED_RELATIONAL_BASELINE"
            if passed
            else "FAIL_DS2_DIAMOND_REGULATED_RELATIONAL_BASELINE"
        ),
        "scope": {
            "validated": (
                "finite dS2 conformal-scalar lattice frequencies, geometry-derived "
                "Type-I KMS/cocycle identities, and regulated relational-map convergence"
            ),
            "continuum_Type_III_to_Type_II_claim": "BLOCKED_NOT_TESTED",
            "gravitational_canonical_energy": "BLOCKED_NOT_TESTED",
            "Einstein_reconstruction": "BLOCKED_NOT_TESTED",
            "multi_observer_global_gluing": "BLOCKED_NOT_TESTED",
        },
        "configuration": config,
        "configuration_sha256": config_hash,
        "source_sha256": source_hashes(),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "geometry": geometry,
        "geometry_mode_kms_cocycle": kms,
        "regulated_relational_embedding": relational,
        "gates": gates,
        "gate_count": {"passed": sum(gates.values()), "total": len(gates)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("ds-diamond-relational.json"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = run()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.strict and not result["status"].startswith("PASS_"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
