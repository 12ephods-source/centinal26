#!/usr/bin/env python3
"""Regulated finite-Type-I KMS/modular/cocycle/BKM falsification harness.

Numerical PASS is deliberately claim-scoped. It does not establish continuum
factor type, emergent geometry, a continuum Connes cocycle, or gravitational
canonical-energy equivalence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np

L = 1.0
BETA = 2.0 * np.pi * L
SEED = 0  # Reserved deterministic contract field; no RNG is used.
FREQS = (1.0, 1.03)
DISPLACEMENTS = (0.35 + 0.20j, -0.25 + 0.15j)
N_CUTS = (4, 5, 6)
EPSILONS = (0.20, 0.10, 0.05, 0.025)
S_VALUES = (-0.25, -0.125, 0.125, 0.25)
COCYCLE_EPS = (0.05, 0.10, 0.20)
DERIVATIVE_STEP = 1.0e-6

UPSTREAM = {
    "clock_regulator_convergence_commit": "58ca997a234ed0010fef30496ec4bbd4b7e99949",
    "finite_type_I_cocycle_commit": "11912a736c9a5e10828bc281af32e389b5c5a33b",
    "bounded_multimode_cocycle_commit": "53698deea8bf002bd502f90a8bef35da37a72e37",
}

THRESHOLDS = {
    "reference_matrix": 1.0e-10,
    "kms": 1.0e-10,
    "cocycle": 1.0e-10,
    "cocycle_generator": 1.0e-7,
    "energy_identity": 1.0e-11,
    "bkm_relative": 1.0e-7,
    "bkm_epsilon_refinement": 1.0e-7,
    "bkm_truncation_refinement": 1.0e-7,
}


def herm(a: np.ndarray) -> np.ndarray:
    return 0.5 * (a + a.conj().T)


def annihilation(n: int) -> np.ndarray:
    if n < 2:
        raise ValueError("n_cut must be >= 2")
    a = np.zeros((n, n), dtype=complex)
    for k in range(1, n):
        a[k - 1, k] = np.sqrt(k)
    return a


def oscillator(n: int, omega: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if omega <= 0:
        raise ValueError("omega must be positive")
    a = annihilation(n)
    number = a.conj().T @ a
    return a, number, omega * number


def spectral_map(a: np.ndarray, fn) -> np.ndarray:
    vals, vecs = np.linalg.eigh(herm(a))
    if float(np.min(vals)) <= 0.0:
        raise FloatingPointError("faithful positive matrix required")
    return (vecs * fn(vals)) @ vecs.conj().T


def rho_log(rho: np.ndarray) -> np.ndarray:
    return spectral_map(rho, np.log)


def rho_it(rho: np.ndarray, s: float) -> np.ndarray:
    return spectral_map(rho, lambda x: np.exp(1j * s * np.log(x)))


def thermal(h: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh(herm(h))
    weights = np.exp(-BETA * (vals - float(np.min(vals))))
    weights /= np.sum(weights)
    return (vecs * weights) @ vecs.conj().T


def antihermitian_exp(k: np.ndarray) -> np.ndarray:
    if np.linalg.norm(k + k.conj().T, ord="fro") > 1.0e-12:
        raise ValueError("generator must be anti-Hermitian")
    vals, vecs = np.linalg.eigh(herm(1j * k))
    return (vecs * np.exp(-1j * vals)) @ vecs.conj().T


def displacement(n: int, amplitude: complex) -> np.ndarray:
    a = annihilation(n)
    return antihermitian_exp(amplitude * a.conj().T - np.conj(amplitude) * a)


def sigma(rho: np.ndarray, s: float, a: np.ndarray) -> np.ndarray:
    u = rho_it(rho, s)
    return u @ a @ u.conj().T


def alpha(h: np.ndarray, t: float, a: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh(herm(h))
    u = (vecs * np.exp(1j * t * vals)) @ vecs.conj().T
    return u @ a @ u.conj().T


def cocycle(rho: np.ndarray, rho0: np.ndarray, s: float) -> np.ndarray:
    return rho_it(rho, s) @ rho_it(rho0, -s)


def relative_entropy(rho: np.ndarray, rho0: np.ndarray) -> float:
    return float(np.real(np.trace(rho @ (rho_log(rho) - rho_log(rho0)))))


def normalized_residual(lhs: np.ndarray, rhs: np.ndarray) -> float:
    denominator = max(
        1.0,
        float(np.linalg.norm(lhs, ord="fro")),
        float(np.linalg.norm(rhs, ord="fro")),
    )
    return float(np.linalg.norm(lhs - rhs, ord="fro") / denominator)


def reference_scan() -> dict[str, float]:
    a, number, h = oscillator(5, 1.0)
    rho0 = thermal(h)
    x = (a + a.conj().T) / np.sqrt(2.0)
    b = number + 0.17 * x

    composition = []
    intertwining = []
    invariance = []
    star = []
    for s in S_VALUES:
        sx = sigma(rho0, s, x)
        intertwining.append(normalized_residual(sx, alpha(h, -BETA * s, x)))
        invariance.append(float(abs(np.trace(rho0 @ sx) - np.trace(rho0 @ x))))
        star.append(
            normalized_residual(sigma(rho0, s, x.conj().T), sx.conj().T)
        )
    for s, t in ((0.25, -0.125), (-0.125, 0.25), (0.125, 0.125)):
        composition.append(
            normalized_residual(
                sigma(rho0, s + t, x),
                sigma(rho0, s, sigma(rho0, t, x)),
            )
        )

    sigma_i_x = np.linalg.inv(rho0) @ x @ rho0
    left = np.trace(rho0 @ sigma_i_x @ b)
    right = np.trace(rho0 @ b @ x)
    kms = float(abs(left - right) / max(1.0, abs(left), abs(right)))

    rho_trace = np.eye(rho0.shape[0], dtype=complex) / rho0.shape[0]
    trace_flow = max(
        normalized_residual(sigma(rho_trace, s, x), x) for s in S_VALUES
    )
    return {
        "rho0_trace_residual": float(abs(np.trace(rho0) - 1.0)),
        "rho0_min_eigenvalue": float(np.min(np.linalg.eigvalsh(rho0))),
        "rho0_stationarity_residual": normalized_residual(rho0 @ h, h @ rho0),
        "modular_composition_max_residual": max(composition),
        "modular_star_max_residual": max(star),
        "modular_state_invariance_max_residual": max(invariance),
        "thermal_modular_static_intertwining_max_residual": max(intertwining),
        "normalized_trace_modular_flow_max_residual": trace_flow,
        "kms_boundary_residual": kms,
    }


def displaced_totals(n: int, epsilon: float) -> dict[str, float]:
    total_s = 0.0
    total_energy = 0.0
    for omega, f in zip(FREQS, DISPLACEMENTS, strict=True):
        _, _, h = oscillator(n, omega)
        rho0 = thermal(h)
        d = displacement(n, epsilon * f)
        rho = d @ rho0 @ d.conj().T
        total_s += relative_entropy(rho, rho0)
        total_energy += float(np.real(np.trace(h @ (rho - rho0))))
    return {"relative_entropy": total_s, "delta_energy": total_energy}


def bkm_scan() -> dict[str, Any]:
    coefficient = float(
        sum(w * abs(f) ** 2 for w, f in zip(FREQS, DISPLACEMENTS, strict=True))
    )
    expected = float(2.0 * BETA * coefficient)
    rows: dict[str, dict[str, dict[str, float]]] = {}
    max_energy_error = 0.0

    for n in N_CUTS:
        n_rows = {}
        for eps in EPSILONS:
            plus = displaced_totals(n, eps)
            minus = displaced_totals(n, -eps)
            energy_error = max(
                abs(plus["relative_entropy"] - BETA * plus["delta_energy"]),
                abs(minus["relative_entropy"] - BETA * minus["delta_energy"]),
            )
            max_energy_error = max(max_energy_error, energy_error)
            fd = (plus["relative_entropy"] + minus["relative_entropy"]) / eps**2
            n_rows[f"{eps:g}"] = {
                "epsilon": eps,
                "bkm_hessian": fd,
                "bkm_relative_error": abs(fd - expected) / expected,
                "energy_identity_max_abs": energy_error,
            }
        rows[str(n)] = n_rows

    n6 = rows["6"]
    eps_refinement = abs(
        n6["0.025"]["bkm_hessian"] - n6["0.05"]["bkm_hessian"]
    ) / expected
    truncation_refinement = abs(
        rows["6"]["0.025"]["bkm_hessian"]
        - rows["5"]["0.025"]["bkm_hessian"]
    ) / expected
    return {
        "analytic_bkm_hessian": expected,
        "normalization_fitted": False,
        "energy_coefficient_sum_omega_abs_f_squared": coefficient,
        "rows": rows,
        "maximum_energy_identity_absolute_error": max_energy_error,
        "n_cut_6_max_bkm_relative_error": max(
            item["bkm_relative_error"] for item in n6.values()
        ),
        "epsilon_0.05_to_0.025_refinement_relative_change": eps_refinement,
        "n_cut_5_to_6_refinement_relative_change": truncation_refinement,
    }


def cocycle_scan() -> dict[str, Any]:
    rows = {}
    maximum_algebraic = 0.0
    maximum_generator = 0.0

    for eps in COCYCLE_EPS:
        a, _, h = oscillator(6, 1.03)
        x = (a + a.conj().T) / np.sqrt(2.0)
        rho0 = thermal(h)
        d1 = displacement(6, eps * (0.31 + 0.17j))
        d2 = displacement(6, eps * (-0.23 + 0.11j))
        rho1 = d1 @ rho0 @ d1.conj().T
        rho2 = d2 @ rho0 @ d2.conj().T

        identity = normalized_residual(cocycle(rho1, rho0, 0.0), np.eye(6))
        unitarity, composition, intertwining, chain = [], [], [], []

        for s in S_VALUES:
            u = cocycle(rho1, rho0, s)
            unitarity.append(normalized_residual(u.conj().T @ u, np.eye(6)))
            intertwining.append(
                normalized_residual(
                    sigma(rho1, s, x),
                    u @ sigma(rho0, s, x) @ u.conj().T,
                )
            )
            chain.append(
                normalized_residual(
                    cocycle(rho2, rho0, s),
                    cocycle(rho2, rho1, s) @ cocycle(rho1, rho0, s),
                )
            )

        for s, t in ((0.25, -0.125), (-0.125, 0.25), (0.125, 0.125)):
            composition.append(
                normalized_residual(
                    cocycle(rho1, rho0, s + t),
                    cocycle(rho1, rho0, s)
                    @ sigma(rho0, s, cocycle(rho1, rho0, t)),
                )
            )

        hstep = DERIVATIVE_STEP
        derivative = (
            cocycle(rho1, rho0, hstep) - cocycle(rho1, rho0, -hstep)
        ) / (2.0 * hstep)
        generator_error = normalized_residual(
            derivative,
            1j * (rho_log(rho1) - rho_log(rho0)),
        )
        algebraic = max(identity, *unitarity, *composition, *intertwining, *chain)
        maximum_algebraic = max(maximum_algebraic, algebraic)
        maximum_generator = max(maximum_generator, generator_error)
        rows[f"{eps:g}"] = {
            "epsilon": eps,
            "maximum_algebraic_residual": algebraic,
            "generator_relative_error": generator_error,
        }

    return {
        "definition": "u_s=rho^(is) rho0^(-is) on a finite Type-I matrix algebra",
        "continuum_claim": False,
        "rows": rows,
        "maximum_algebraic_residual": maximum_algebraic,
        "maximum_generator_relative_error": maximum_generator,
    }


def configuration() -> dict[str, Any]:
    return {
        "de_sitter_radius_L": L,
        "beta_dS_formula": "2*pi*L",
        "beta_dS": float(BETA),
        "frequencies": list(FREQS),
        "displacements": [
            {"real": f.real, "imag": f.imag} for f in DISPLACEMENTS
        ],
        "n_cut_scan": list(N_CUTS),
        "epsilon_scan": list(EPSILONS),
        "modular_parameter_scan": list(S_VALUES),
        "cocycle_epsilon_scan": list(COCYCLE_EPS),
        "derivative_step": DERIVATIVE_STEP,
    }


def configuration_sha256() -> str:
    encoded = json.dumps(
        {"seed": SEED, "configuration": configuration(), "thresholds": THRESHOLDS},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_harness() -> dict[str, Any]:
    reference = reference_scan()
    bkm = bkm_scan()
    cocycle_result = cocycle_scan()

    reference_max = max(
        reference[key]
        for key in (
            "rho0_trace_residual",
            "rho0_stationarity_residual",
            "modular_composition_max_residual",
            "modular_star_max_residual",
            "modular_state_invariance_max_residual",
            "thermal_modular_static_intertwining_max_residual",
            "normalized_trace_modular_flow_max_residual",
        )
    )
    gates = {
        "reference_modular_identities": (
            reference_max <= THRESHOLDS["reference_matrix"]
            and reference["kms_boundary_residual"] <= THRESHOLDS["kms"]
        ),
        "finite_type_I_cocycle": (
            cocycle_result["maximum_algebraic_residual"] <= THRESHOLDS["cocycle"]
            and cocycle_result["maximum_generator_relative_error"]
            <= THRESHOLDS["cocycle_generator"]
        ),
        "relative_entropy_matter_energy_identity": (
            bkm["maximum_energy_identity_absolute_error"]
            <= THRESHOLDS["energy_identity"]
        ),
        "bkm_analytic_normalization": (
            bkm["n_cut_6_max_bkm_relative_error"] <= THRESHOLDS["bkm_relative"]
        ),
        "bkm_epsilon_regulator_convergence": (
            bkm["epsilon_0.05_to_0.025_refinement_relative_change"]
            <= THRESHOLDS["bkm_epsilon_refinement"]
        ),
        "bkm_truncation_regulator_convergence": (
            bkm["n_cut_5_to_6_refinement_relative_change"]
            <= THRESHOLDS["bkm_truncation_refinement"]
        ),
    }
    gate4 = (
        gates["relative_entropy_matter_energy_identity"]
        and gates["bkm_analytic_normalization"]
        and gates["bkm_epsilon_regulator_convergence"]
        and gates["bkm_truncation_regulator_convergence"]
    )
    passed = all(gates.values())

    return {
        "schema": "frost.phase1.regulated-kms-modular-cocycle-falsification.v2",
        "status": (
            "PASS_REGULATED_KMS_MODULAR_COCYCLE_BKM_BASELINE" if passed else "FAIL"
        ),
        "determinism": {
            "seed": SEED,
            "randomness_used": False,
            "seed_semantics": "reserved deterministic contract field; no RNG is used",
            "json_keys": "sorted",
        },
        "analytic_normalization": {
            "de_sitter_radius_L": L,
            "unit_convention": "dimensionless de Sitter units with L=1",
            "beta_dS_formula": "2*pi*L",
            "beta_dS": float(BETA),
            "modular_generator": "K_mod=-log(rho0)=beta_dS*H_st+constant*I",
            "bkm_hessian_formula": "2*beta_dS*sum_k(omega_k*|f_k|^2)",
            "fitted_constants": False,
        },
        "parameters": configuration(),
        "regulator": {
            "finite_type_I_truncations": list(N_CUTS),
            "finite_difference_epsilons": list(EPSILONS),
            "upstream_verified_regulator_evidence": UPSTREAM,
            "scope": (
                "this harness independently checks BKM truncation/epsilon convergence; "
                "clock and multi-mode regulator evidence is inherited from merged main"
            ),
        },
        "scope": {
            "numerical_algebra": "finite Type-I matrix algebra only",
            "continuum_type_chain": (
                "Type III_1 modular data -> Type II_infinity crossed product -> "
                "Type II_1 finite corner via regulated CLPW positive-energy projection"
            ),
            "not_established": [
                "continuum Type III_1 factor",
                "continuum Type II_infinity crossed product",
                "Type II_1 CLPW finite corner",
                "continuum Connes cocycle",
                "emergent geometry",
                "BKM-Hollands-Wald canonical-energy equivalence",
            ],
        },
        "thresholds": THRESHOLDS,
        "gates": gates,
        "gate_accounting": {
            "Gate_1_Geometric_Reference_Model": {
                "numerical_status": (
                    "PASS_FINITE_KMS_MODULAR_REFERENCE_PROXY"
                    if gates["reference_modular_identities"]
                    else "FAIL"
                ),
                "continuum_status": "NOT_ESTABLISHED_BY_FINITE_MATRICES",
            },
            "Gate_2_Quantum_Clock_Constraint_Invariance": {
                "status": "UPSTREAM_VERIFIED_REGULATOR_EVIDENCE",
                "evidence_commit": UPSTREAM["clock_regulator_convergence_commit"],
            },
            "Gate_3_Crossed_Product_Algebra_And_Type": {
                "numerical_status": (
                    "PASS_FINITE_TYPE_I_COCYCLE_SURROGATE"
                    if gates["finite_type_I_cocycle"]
                    else "FAIL"
                ),
                "continuum_type_status": "ANALYTIC_TARGET_ONLY",
            },
            "Gate_4_Relative_Entropy_BKM_Matter_Energy_Baseline": {
                "definition_status": "CANONICALIZED_IN_SCHEMA_V2",
                "historical_recovery_status": (
                    "NO_PRIOR_SEPARATE_GATE_4_DEFINITION_RECOVERED"
                ),
                "numerical_status": (
                    "PASS_FINITE_TYPE_I_MATTER_BASELINE" if gate4 else "FAIL"
                ),
                "scope": (
                    "relative entropy and BKM matter/Killing-energy identities only; "
                    "no gravitational canonical-energy equivalence"
                ),
            },
            "Gate_5": "PROPOSED",
            "Gate_6": "PROPOSED",
        },
        "reference": reference,
        "finite_type_I_cocycle": cocycle_result,
        "bkm": bkm,
        "provenance": {
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "configuration_sha256": configuration_sha256(),
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run_harness()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
        print(report["status"])
    else:
        print(text, end="")
    return 1 if args.strict and report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
