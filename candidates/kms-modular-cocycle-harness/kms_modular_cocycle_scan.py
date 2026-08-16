#!/usr/bin/env python3
"""Finite-Type-I KMS/modular/cocycle falsification harness.

This NumPy-only surrogate tests algebraic identities and convergence. It does not
establish a continuum Type-II/III algebra, spacetime reconstruction, or
Hollands-Wald canonical energy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np

BETA = 2.0 * np.pi
FREQS = (1.0, 1.03)
F = (0.35 + 0.20j, -0.25 + 0.15j)
N_SCAN = (3, 4, 5)
EPS_SCAN = (0.2, 0.1, 0.05, 0.025)
S_SCAN = (-0.25, -0.125, 0.125, 0.25)
COCYCLE_EPS = (0.05, 0.1, 0.2)
Q_MAX, DQ, SIGMA_RATIO = 8.0, 0.25, 1.0 / 16.0
THRESH = {
    "matrix": 1e-10,
    "kms": 1e-10,
    "cocycle": 1e-10,
    "cocycle_generator": 1e-7,
    "energy_identity": 1e-11,
    "bkm": 1e-7,
    "bkm_refinement": 1e-7,
    "nontrivial_motion": 1e-3,
    "clock_min_eigenvalue": -1e-12,
    "clock_closure": 1e-12,
}


def herm(a: np.ndarray) -> np.ndarray:
    return 0.5 * (a + a.conj().T)


def annihilation(n: int) -> np.ndarray:
    if n < 2:
        raise ValueError("n_cut must be >=2")
    a = np.zeros((n, n), complex)
    for k in range(1, n):
        a[k - 1, k] = np.sqrt(k)
    return a


def oscillator(n: int, omega: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if omega <= 0:
        raise ValueError("omega must be positive")
    a = annihilation(n)
    num = a.conj().T @ a
    return a, num, omega * num


def spectral_map(a: np.ndarray, fn) -> np.ndarray:
    vals, vecs = np.linalg.eigh(herm(a))
    if np.min(vals) <= 0:
        raise FloatingPointError("faithful positive matrix required")
    return (vecs * fn(vals)) @ vecs.conj().T


def rho_log(rho: np.ndarray) -> np.ndarray:
    return spectral_map(rho, np.log)


def rho_it(rho: np.ndarray, s: float) -> np.ndarray:
    return spectral_map(rho, lambda x: np.exp(1j * s * np.log(x)))


def thermal(h: np.ndarray, beta: float = BETA) -> np.ndarray:
    vals, vecs = np.linalg.eigh(herm(h))
    weights = np.exp(-beta * (vals - np.min(vals)))
    weights /= np.sum(weights)
    return (vecs * weights) @ vecs.conj().T


def exp_anti(k: np.ndarray) -> np.ndarray:
    if np.linalg.norm(k.conj().T + k, "fro") > 1e-12:
        raise ValueError("generator must be anti-Hermitian")
    vals, vecs = np.linalg.eigh(herm(1j * k))
    return (vecs * np.exp(-1j * vals)) @ vecs.conj().T


def displace(n: int, amplitude: complex) -> np.ndarray:
    a = annihilation(n)
    return exp_anti(amplitude * a.conj().T - np.conj(amplitude) * a)


def sigma(rho: np.ndarray, s: float, a: np.ndarray) -> np.ndarray:
    u = rho_it(rho, s)
    return u @ a @ u.conj().T


def alpha(h: np.ndarray, t: float, a: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh(herm(h))
    u = (vecs * np.exp(1j * t * vals)) @ vecs.conj().T
    return u @ a @ u.conj().T


def cocycle(rho: np.ndarray, rho0: np.ndarray, s: float) -> np.ndarray:
    return rho_it(rho, s) @ rho_it(rho0, -s)


def rel_entropy(rho: np.ndarray, sigma0: np.ndarray) -> float:
    return float(np.real(np.trace(rho @ (rho_log(rho) - rho_log(sigma0)))))


def nr(lhs: np.ndarray, rhs: np.ndarray) -> float:
    den = max(1.0, np.linalg.norm(lhs, "fro"), np.linalg.norm(rhs, "fro"))
    return float(np.linalg.norm(lhs - rhs, "fro") / den)


def reference_metrics() -> dict[str, Any]:
    n = 4
    a, num, h = oscillator(n, 1.0)
    rho0 = thermal(h)
    x = (a + a.conj().T) / np.sqrt(2.0)
    b = num + 0.17 * x
    comp, star, inv, inter, motion = [], [], [], [], []
    for s in S_SCAN:
        sx = sigma(rho0, s, x)
        star.append(nr(sigma(rho0, s, x.conj().T), sx.conj().T))
        inv.append(float(abs(np.trace(rho0 @ sx) - np.trace(rho0 @ x))))
        inter.append(nr(sx, alpha(h, -BETA * s, x)))
        motion.append(float(np.linalg.norm(sx - x, "fro")))
    for s, t in ((0.25, -0.125), (-0.125, 0.25), (0.125, 0.125)):
        comp.append(
            nr(
                sigma(rho0, s + t, x),
                sigma(rho0, s, sigma(rho0, t, x)),
            )
        )

    # For sigma_s(A)=rho^{is}A rho^{-is}: omega(sigma_i(A)B)=omega(BA).
    sig_i_x = np.linalg.inv(rho0) @ x @ rho0
    left, right = np.trace(rho0 @ sig_i_x @ b), np.trace(rho0 @ b @ x)
    kms = float(abs(left - right) / max(1.0, abs(left), abs(right)))
    rho_trace = np.eye(n, dtype=complex) / n
    trace_mod = max(nr(sigma(rho_trace, s, x), x) for s in S_SCAN)
    return {
        "n_cut": n,
        "beta_dS": float(BETA),
        "rho0_trace_residual": float(abs(np.trace(rho0) - 1.0)),
        "rho0_min_eigenvalue": float(np.min(np.linalg.eigvalsh(rho0))),
        "rho0_stationarity_residual": nr(rho0 @ h, h @ rho0),
        "modular_composition_max_residual": max(comp),
        "modular_star_max_residual": max(star),
        "modular_state_invariance_max_residual": max(inv),
        "reference_modular_to_static_flow_max_residual": max(inter),
        "reference_modular_motion_min_frobenius": min(motion),
        "kms_boundary_residual": kms,
        "normalized_trace_modular_flow_max_residual": trace_mod,
    }


def clock_metrics() -> dict[str, Any]:
    n_intervals = round(Q_MAX / DQ)
    q = np.arange(n_intervals + 1, dtype=float) * DQ
    if q[0] < 0 or abs(q[-1] - Q_MAX) > 1e-12:
        raise AssertionError("positive clock grid invalid")
    period, tau, sigma_tau = 2 * np.pi / DQ, np.pi / DQ, SIGMA_RATIO * BETA
    d = q[:, None] - q[None, :]
    g = np.exp(-0.5 * (sigma_tau * d) ** 2)
    effect = np.exp(-1j * d * tau) * g / period
    n_tau = 2 * q.size
    tau_grid = np.arange(n_tau) * period / n_tau
    integrated = g * np.exp(-1j * d[..., None] * tau_grid).mean(axis=-1)
    return {
        "continuum_target": "H_obs=q on L2(R_+), q>=0",
        "q_min": float(q[0]),
        "q_max": float(q[-1]),
        "delta_q": DQ,
        "N_q": int(q.size),
        "sigma_tau_over_beta": SIGMA_RATIO,
        "recurrence_P": float(period),
        "tau": float(tau),
        "uses_distributional_time_projector": False,
        "uses_smeared_povm_effect": True,
        "minimum_effect_eigenvalue": float(
            np.min(np.linalg.eigvalsh(herm(effect)))
        ),
        "endpoint_free_povm_closure_residual": float(
            np.linalg.norm(integrated - np.eye(q.size), "fro")
        ),
    }


def coherent_totals(n: int, epsilon: float) -> dict[str, float]:
    total_s = total_e = 0.0
    min_eig, max_unit = 1.0, 0.0
    for omega, f in zip(FREQS, F, strict=True):
        _, _, h = oscillator(n, omega)
        rho0 = thermal(h)
        d = displace(n, epsilon * f)
        rho = d @ rho0 @ d.conj().T
        total_s += rel_entropy(rho, rho0)
        total_e += float(np.real(np.trace(h @ (rho - rho0))))
        min_eig = min(
            min_eig,
            float(np.min(np.linalg.eigvalsh(herm(rho)))),
        )
        max_unit = max(
            max_unit,
            float(np.linalg.norm(d.conj().T @ d - np.eye(n), "fro")),
        )
    return {"S": total_s, "dE": total_e, "min_eig": min_eig, "unitarity": max_unit}


def bkm_scan() -> dict[str, Any]:
    coeff = float(sum(w * abs(f) ** 2 for w, f in zip(FREQS, F, strict=True)))
    expected = float(2 * BETA * coeff)
    scans, max_energy_error = {}, 0.0
    for n in N_SCAN:
        rows = {}
        for eps in EPS_SCAN:
            plus, minus = coherent_totals(n, eps), coherent_totals(n, -eps)
            analytic_s = BETA * eps**2 * coeff
            energy_error = max(
                abs(plus["S"] - BETA * plus["dE"]),
                abs(minus["S"] - BETA * minus["dE"]),
            )
            max_energy_error = max(max_energy_error, energy_error)
            fd = (plus["S"] + minus["S"]) / eps**2
            rows[f"epsilon_{eps:g}"] = {
                "epsilon": eps,
                "relative_entropy_plus": plus["S"],
                "relative_entropy_minus": minus["S"],
                "beta_delta_energy_plus": BETA * plus["dE"],
                "beta_delta_energy_minus": BETA * minus["dE"],
                "S_minus_beta_deltaE_max_abs": energy_error,
                "analytic_infinite_mode_relative_entropy": analytic_s,
                "bkm_hessian_central_finite_difference": fd,
                "bkm_expected_analytic": expected,
                "bkm_relative_error": abs(fd - expected) / expected,
                "relative_entropy_odd_asymmetry": abs(plus["S"] - minus["S"])
                / analytic_s,
                "minimum_state_eigenvalue": min(plus["min_eig"], minus["min_eig"]),
                "max_displacement_unitarity_residual": max(
                    plus["unitarity"], minus["unitarity"]
                ),
            }
        scans[f"n_cut_{n}"] = rows
    n5 = scans["n_cut_5"]
    e05 = n5["epsilon_0.05"]["bkm_hessian_central_finite_difference"]
    e025 = n5["epsilon_0.025"]["bkm_hessian_central_finite_difference"]
    return {
        "frequencies": list(FREQS),
        "displacements": [{"real": f.real, "imag": f.imag} for f in F],
        "energy_coefficient_sum_omega_abs_f_squared": coeff,
        "analytic_bkm_hessian": expected,
        "normalization_fitted": False,
        "interpretation": (
            "matter modular/Killing energy only; not gravitational canonical energy"
        ),
        "scan": scans,
        "maximum_S_minus_beta_deltaE_absolute": max_energy_error,
        "n_cut_5_max_bkm_relative_error": max(
            row["bkm_relative_error"] for row in n5.values()
        ),
        "n_cut_5_epsilon_0.05_to_0.025_refinement_relative_change": abs(e05 - e025)
        / expected,
    }


def cocycle_scan() -> dict[str, Any]:
    rows, global_max, gen_max = {}, 0.0, 0.0
    for n in N_SCAN:
        a, _, h = oscillator(n, 1.03)
        x, rho0 = (a + a.conj().T) / np.sqrt(2.0), thermal(h)
        for eps in COCYCLE_EPS:
            d1 = displace(n, eps * (0.31 + 0.17j))
            d2 = displace(n, eps * (-0.23 + 0.11j))
            rho1 = d1 @ rho0 @ d1.conj().T
            rho2 = d2 @ rho0 @ d2.conj().T
            zero = nr(cocycle(rho1, rho0, 0), np.eye(n))
            unit, comp, inter, chain = [], [], [], []
            for s in S_SCAN:
                us = cocycle(rho1, rho0, s)
                unit.append(nr(us.conj().T @ us, np.eye(n)))
                inter.append(
                    nr(
                        sigma(rho1, s, x),
                        us @ sigma(rho0, s, x) @ us.conj().T,
                    )
                )
                chain.append(
                    nr(
                        cocycle(rho2, rho0, s),
                        cocycle(rho2, rho1, s) @ cocycle(rho1, rho0, s),
                    )
                )
            for s, t in ((0.25, -0.125), (-0.125, 0.25), (0.125, 0.125)):
                comp.append(
                    nr(
                        cocycle(rho1, rho0, s + t),
                        cocycle(rho1, rho0, s)
                        @ sigma(rho0, s, cocycle(rho1, rho0, t)),
                    )
                )
            step = 1e-6
            deriv = (
                cocycle(rho1, rho0, step) - cocycle(rho1, rho0, -step)
            ) / (2 * step)
            gen = nr(deriv, 1j * (rho_log(rho1) - rho_log(rho0)))
            vals = [zero, *unit, *comp, *inter, *chain]
            global_max, gen_max = max(global_max, *vals), max(gen_max, gen)
            rows[f"n{n}_epsilon_{eps:g}"] = {
                "n_cut": n,
                "epsilon": eps,
                "identity_at_zero_residual": zero,
                "unitarity_max_residual": max(unit),
                "cocycle_composition_max_residual": max(comp),
                "modular_intertwining_max_residual": max(inter),
                "chain_rule_max_residual": max(chain),
                "generator_relative_error": gen,
                "rho0_min_eigenvalue": float(np.min(np.linalg.eigvalsh(rho0))),
                "rho1_min_eigenvalue": float(
                    np.min(np.linalg.eigvalsh(herm(rho1)))
                ),
            }
    return {
        "definition": "u_s=rho^{is} rho0^{-is} on the finite Type-I surrogate",
        "continuum_claim": False,
        "rows": rows,
        "maximum_algebraic_residual": global_max,
        "maximum_generator_relative_error": gen_max,
    }


def config_hash() -> str:
    payload = {
        "beta": BETA,
        "freqs": FREQS,
        "f": [(z.real, z.imag) for z in F],
        "n": N_SCAN,
        "eps": EPS_SCAN,
        "s": S_SCAN,
        "cocycle_eps": COCYCLE_EPS,
        "clock": (Q_MAX, DQ, SIGMA_RATIO),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_harness() -> dict[str, Any]:
    ref, clock, bkm, coc = reference_metrics(), clock_metrics(), bkm_scan(), cocycle_scan()
    ref_max = max(
        ref[k]
        for k in (
            "rho0_trace_residual",
            "rho0_stationarity_residual",
            "modular_composition_max_residual",
            "modular_star_max_residual",
            "modular_state_invariance_max_residual",
            "reference_modular_to_static_flow_max_residual",
            "normalized_trace_modular_flow_max_residual",
        )
    )
    gates = {
        "finite_reference_matrix_identities": ref_max <= THRESH["matrix"],
        "kms_boundary": ref["kms_boundary_residual"] <= THRESH["kms"],
        "trace_modular_flow_is_trivial": (
            ref["normalized_trace_modular_flow_max_residual"] <= THRESH["matrix"]
        ),
        "thermal_reference_modular_flow_is_nontrivial": (
            ref["reference_modular_motion_min_frobenius"]
            >= THRESH["nontrivial_motion"]
        ),
        "positive_energy_smeared_clock_effect": (
            clock["minimum_effect_eigenvalue"] >= THRESH["clock_min_eigenvalue"]
            and clock["endpoint_free_povm_closure_residual"]
            <= THRESH["clock_closure"]
        ),
        "finite_type_I_cocycle_identities": (
            coc["maximum_algebraic_residual"] <= THRESH["cocycle"]
            and coc["maximum_generator_relative_error"]
            <= THRESH["cocycle_generator"]
        ),
        "relative_entropy_equals_beta_matter_energy_change": (
            bkm["maximum_S_minus_beta_deltaE_absolute"] <= THRESH["energy_identity"]
        ),
        "bkm_analytic_baseline_at_ncut5": (
            bkm["n_cut_5_max_bkm_relative_error"] <= THRESH["bkm"]
        ),
        "bkm_finite_difference_refinement": (
            bkm["n_cut_5_epsilon_0.05_to_0.025_refinement_relative_change"]
            <= THRESH["bkm_refinement"]
        ),
    }
    passed = all(gates.values())
    return {
        "schema": "frost.phase1.kms-modular-cocycle-falsification.v1",
        "status": (
            "PASS_FINITE_TYPE_I_KMS_MODULAR_COCYCLE_BASELINE" if passed else "FAIL"
        ),
        "scope": {
            "purpose": "falsification and convergence testing, not optimization",
            "algebra_type_of_numerical_model": "Type I matrix algebra only",
            "continuum_targets_not_numerically_established": [
                "M_O Type III_1",
                "crossed product Type II_infinity",
                "positive-energy corner Type II_1",
                "continuum Connes cocycle",
            ],
            "forbidden_claims": [
                "crossed product derives spacetime or matter",
                "tracial modular flow equals clock evolution",
                "BKM matter-energy test verifies gravitational canonical energy",
                "Gate 5 verified",
                "Gate 6 verified",
            ],
        },
        "conventions": {
            "thermal_state": "rho0=Z^-1 exp(-beta_dS H_st)",
            "beta_dS": float(BETA),
            "modular_flow": "sigma_s^rho(A)=rho^{is} A rho^{-is}",
            "thermal_static_intertwining": "sigma_s^rho0=alpha_{-beta_dS*s}^st",
            "cocycle": "u_s=rho^{is} rho0^{-is}",
            "clock": (
                "H_obs=q>=0 with smeared POVM time effect; no exact self-adjoint "
                "canonical time asserted"
            ),
        },
        "thresholds": THRESH,
        "gates": gates,
        "gate_accounting": {
            "Gate_1_Geometric_Reference_Model": {
                "numerical_status": (
                    "PASS_FINITE_KMS_MODULAR_REFERENCE_PROXY"
                    if gates["finite_reference_matrix_identities"]
                    and gates["kms_boundary"]
                    else "FAIL"
                ),
                "continuum_status": "NOT_VERIFIED_BY_FINITE_MATRIX_HARNESS",
            },
            "Gate_2_Quantum_Clock_Constraint_Invariance": {
                "numerical_status": (
                    "POVM_SANITY_PASS_DEPENDS_ON_PR83_FOR_FULL_REGULATOR_CONVERGENCE"
                    if gates["positive_energy_smeared_clock_effect"]
                    else "FAIL"
                ),
                "continuum_status": "NOT_VERIFIED",
            },
            "Gate_3_Crossed_Product_Algebra_And_Type": {
                "numerical_status": (
                    "FINITE_TYPE_I_COCYCLE_IDENTITIES_PASS"
                    if gates["finite_type_I_cocycle_identities"]
                    else "FAIL"
                ),
                "continuum_type_status": (
                    "ANALYTIC_TARGET_ONLY_NOT_INFERRED_FROM_FINITE_MATRICES"
                ),
            },
            "Gate_5": "PROPOSED",
            "Gate_6": "PROPOSED",
            "higher_order_reconstruction": "OPEN_SEPARATE_GATE",
        },
        "reference_model": ref,
        "clock_regulator": clock,
        "bkm_matter_energy": bkm,
        "finite_type_I_cocycle": coc,
        "provenance": {
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "configuration_sha256": config_hash(),
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
        print(f"wrote {args.output}\n{report['status']}")
    else:
        print(text, end="")
    return 1 if args.strict and report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
