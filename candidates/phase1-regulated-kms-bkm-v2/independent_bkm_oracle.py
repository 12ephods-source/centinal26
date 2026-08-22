from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

L = 1.0
BETA = 2.0 * math.pi * L
FREQS = (1.0, 1.03)
DISPLACEMENTS = (0.35 + 0.20j, -0.25 + 0.15j)
N_CUTS = (4, 5, 6, 7)
STRESS_FREQS = (0.5, 2.3)
STRESS_DISPLACEMENTS = (0.41 - 0.13j, -0.22 + 0.37j)
EPSILONS = (0.20, 0.10, 0.05, 0.025)

THRESHOLDS = {
    "fd_vs_divided_difference_relative": 1.0e-6,
    "n7_vs_analytic_relative": 1.0e-9,
    "truncation_refinement_relative": 1.0e-8,
    "negative_control_min_relative_separation": 0.10,
    "unitarity_residual": 1.0e-12,
    "trace_residual": 1.0e-12,
}


def annihilation(n: int) -> np.ndarray:
    if n < 2:
        raise ValueError("n_cut must be >= 2")
    a = np.zeros((n, n), dtype=np.complex128)
    idx = np.arange(1, n)
    a[idx - 1, idx] = np.sqrt(idx)
    return a


def thermal_probabilities(n: int, omega: float) -> np.ndarray:
    if omega <= 0:
        raise ValueError("omega must be positive")
    energies = omega * np.arange(n, dtype=float)
    shifted = -BETA * (energies - energies.min())
    p = np.exp(shifted)
    p /= p.sum()
    if not np.all(np.isfinite(p)) or np.any(p <= 0.0):
        raise FloatingPointError("thermal state must be faithful")
    return p


def unitary_from_generator(g: np.ndarray, epsilon: float) -> np.ndarray:
    antiherm_res = np.linalg.norm(g + g.conj().T, ord="fro")
    if antiherm_res > 1.0e-12:
        raise ValueError("generator is not anti-Hermitian")
    vals, vecs = np.linalg.eigh(0.5 * (1j * g + (1j * g).conj().T))
    u = (vecs * np.exp(-1j * epsilon * vals)) @ vecs.conj().T
    resid = np.linalg.norm(u.conj().T @ u - np.eye(u.shape[0]), ord="fro")
    if resid > THRESHOLDS["unitarity_residual"]:
        raise FloatingPointError("unitarity check failed")
    return u


def generator(n: int, f: complex) -> np.ndarray:
    a = annihilation(n)
    return f * a.conj().T - np.conj(f) * a


def relative_entropy_eigenbasis(p: np.ndarray, u: np.ndarray) -> float:
    """Independent Umegaki S(U diag(p) U^† || diag(p))."""
    if p.ndim != 1 or u.shape != (p.size, p.size):
        raise ValueError("dimension mismatch")
    if np.any(p <= 0.0):
        raise FloatingPointError("reference state must be faithful")
    weights = np.abs(u) ** 2
    col_resid = np.max(np.abs(weights.sum(axis=0) - 1.0))
    if col_resid > THRESHOLDS["trace_residual"]:
        raise FloatingPointError("transition probabilities are not normalized")
    logp = np.log(p)
    tr_rho_log_rho = float(np.dot(p, logp))
    rho_diag = weights @ p
    tr_rho_log_rho0 = float(np.dot(rho_diag, logp))
    s = tr_rho_log_rho - tr_rho_log_rho0
    if s < -1.0e-12:
        raise FloatingPointError("relative entropy became negative")
    return max(0.0, s)


def divided_difference_hessian(p: np.ndarray, g: np.ndarray) -> float:
    """Exact finite-dimensional Umegaki Hessian along a unitary orbit."""
    if np.any(p <= 0.0):
        raise FloatingPointError("reference state must be faithful")
    delta = g * (p[np.newaxis, :] - p[:, np.newaxis])
    out = 0.0
    for i, pi in enumerate(p):
        for j, pj in enumerate(p):
            dij2 = float(abs(delta[i, j]) ** 2)
            if dij2 == 0.0:
                continue
            if i == j or abs(pi - pj) <= 1.0e-15 * max(pi, pj):
                kernel = 1.0 / pi
            else:
                kernel = (math.log(pi) - math.log(pj)) / (pi - pj)
            out += dij2 * kernel
    return float(out)


def mode_scan(n: int, omega: float, f: complex) -> dict[str, Any]:
    p = thermal_probabilities(n, omega)
    g = generator(n, f)
    hessian_exact = divided_difference_hessian(p, g)
    fd_rows = []
    for eps in EPSILONS:
        up = unitary_from_generator(g, eps)
        um = unitary_from_generator(g, -eps)
        sp = relative_entropy_eigenbasis(p, up)
        sm = relative_entropy_eigenbasis(p, um)
        fd = (sp + sm) / (eps * eps)
        rel = abs(fd - hessian_exact) / max(abs(hessian_exact), 1.0e-300)
        fd_rows.append(
            {
                "epsilon": eps,
                "S_plus": sp,
                "S_minus": sm,
                "finite_difference_hessian": fd,
                "relative_error_vs_divided_difference": rel,
            }
        )
    return {
        "omega": omega,
        "f_real": float(np.real(f)),
        "f_imag": float(np.imag(f)),
        "reference_min_probability": float(p.min()),
        "divided_difference_hessian": hessian_exact,
        "finite_difference": fd_rows,
    }


def run() -> dict[str, Any]:
    analytic = 2.0 * BETA * sum(
        omega * abs(f) ** 2 for omega, f in zip(FREQS, DISPLACEMENTS, strict=True)
    )
    by_cut = {}
    max_fd_rel = 0.0
    totals = {}
    for n in N_CUTS:
        modes = [mode_scan(n, w, f) for w, f in zip(FREQS, DISPLACEMENTS, strict=True)]
        exact_total = sum(m["divided_difference_hessian"] for m in modes)
        totals[n] = exact_total
        for m in modes:
            for row in m["finite_difference"]:
                max_fd_rel = max(max_fd_rel, row["relative_error_vs_divided_difference"])
        by_cut[str(n)] = {
            "modes": modes,
            "total_divided_difference_hessian": exact_total,
            "relative_error_vs_infinite_analytic": abs(exact_total - analytic) / analytic,
        }

    trunc_refine = abs(totals[7] - totals[6]) / analytic
    n7_rel = abs(totals[7] - analytic) / analytic
    wrong_targets = {
        "missing_factor_2": 0.5 * analytic,
        "wrong_beta_half": 0.5 * analytic,
    }
    neg_sep = {
        name: abs(totals[7] - target) / analytic for name, target in wrong_targets.items()
    }

    stress_analytic = 2.0 * BETA * sum(
        omega * abs(f) ** 2
        for omega, f in zip(STRESS_FREQS, STRESS_DISPLACEMENTS, strict=True)
    )
    stress_exact = sum(
        mode_scan(12, omega, f)["divided_difference_hessian"]
        for omega, f in zip(STRESS_FREQS, STRESS_DISPLACEMENTS, strict=True)
    )
    stress_frequency_blind = 2.0 * BETA * sum(abs(f) ** 2 for f in STRESS_DISPLACEMENTS)
    stress_correct_rel = abs(stress_exact - stress_analytic) / stress_analytic
    stress_frequency_blind_sep = abs(stress_exact - stress_frequency_blind) / stress_analytic
    neg_sep["frequency_blind_stress_fixture"] = stress_frequency_blind_sep
    min_neg_sep = min(neg_sep.values())

    gates = {
        "finite_difference_matches_independent_divided_difference": max_fd_rel
        <= THRESHOLDS["fd_vs_divided_difference_relative"],
        "high_cut_matches_infinite_coherent_analytic": n7_rel
        <= THRESHOLDS["n7_vs_analytic_relative"],
        "truncation_refinement": trunc_refine
        <= THRESHOLDS["truncation_refinement_relative"],
        "negative_controls_rejected": min_neg_sep
        >= THRESHOLDS["negative_control_min_relative_separation"],
        "frequency_weighting_stress_fixture": stress_correct_rel
        <= THRESHOLDS["n7_vs_analytic_relative"],
    }
    return {
        "schema": "frost.phase1.bkm-independent-oracle.v1",
        "status": "PASS_INDEPENDENT_BKM_ORACLE" if all(gates.values()) else "FAIL",
        "scope": {
            "algebra": "finite Type-I oscillator truncations only",
            "continuum_claim": False,
            "purpose": "orthogonal oracle for the canonical Phase-I v2 BKM baseline",
        },
        "normalization": {
            "L": L,
            "beta_dS": BETA,
            "analytic_infinite_hessian": analytic,
            "formula": "2*beta_dS*sum_k(omega_k*|f_k|^2)",
        },
        "thresholds": THRESHOLDS,
        "gates": gates,
        "diagnostics": {
            "max_fd_relative_error_vs_divided_difference": max_fd_rel,
            "n_cut_7_relative_error_vs_infinite_analytic": n7_rel,
            "n_cut_6_to_7_refinement_relative_change": trunc_refine,
            "negative_control_relative_separations": neg_sep,
            "minimum_negative_control_relative_separation": min_neg_sep,
            "stress_fixture_correct_relative_error": stress_correct_rel,
            "stress_fixture_frequency_blind_relative_separation": stress_frequency_blind_sep,
        },
        "cuts": by_cut,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
