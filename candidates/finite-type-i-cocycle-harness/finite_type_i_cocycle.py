#!/usr/bin/env python3
"""
Finite-Type-I Connes cocycle consistency harness.

Scope boundary:
  * finite-dimensional Type-I matrix algebra only;
  * faithful states with known spectral frames;
  * no claim of Type-II/Type-III realization or continuum Connes cocycle.

The central numerical design choice is floor-free spectral functional calculus.
Instead of diagonalizing an ill-conditioned density matrix and clipping tiny
weights, each faithful state stores its unitary spectral frame and normalized
log-weights. Matrix powers and logarithms are constructed directly from that
representation. This preserves thermal weights far below 1e-15 whenever their
log-weights remain representable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA = "frost.phase1.finite_type_i_cocycle.v1"
DEFAULT_BETA = 2.0 * math.pi
S_VALUES = (-0.5, -0.25, -0.125, 0.125, 0.25, 0.5)
PAIR_VALUES = ((0.125, 0.25), (-0.125, 0.5), (0.25, -0.5))


def fro_norm(x: np.ndarray) -> float:
    return float(np.linalg.norm(x, "fro"))


def relative_fro_residual(x: np.ndarray, y: np.ndarray) -> float:
    return fro_norm(x - y) / max(fro_norm(x), fro_norm(y), 1e-300)


def annihilation(n: int) -> np.ndarray:
    a = np.zeros((n, n), dtype=complex)
    for k in range(1, n):
        a[k - 1, k] = math.sqrt(k)
    return a


def unitary_from_antihermitian(generator: np.ndarray) -> np.ndarray:
    """Return exp(generator) for anti-Hermitian generator using Hermitian eigh."""
    anti_res = fro_norm(generator.conj().T + generator)
    if anti_res > 1e-11:
        raise ValueError(f"generator is not anti-Hermitian: residual={anti_res}")
    hermitian = 1j * generator
    evals, vecs = np.linalg.eigh(0.5 * (hermitian + hermitian.conj().T))
    return (vecs * np.exp(-1j * evals)) @ vecs.conj().T


def displacement(n: int, alpha: complex) -> np.ndarray:
    a = annihilation(n)
    adag = a.conj().T
    generator = alpha * adag - np.conj(alpha) * a
    return unitary_from_antihermitian(generator)


def normalized_thermal_log_weights(n: int, beta: float, omega: float) -> np.ndarray:
    """Stable normalized log Gibbs weights, without ever applying a probability floor."""
    exponents = -beta * omega * np.arange(n, dtype=float)
    pivot = float(np.max(exponents))
    log_z = pivot + math.log(float(np.exp(exponents - pivot).sum()))
    return exponents - log_z


@dataclass(frozen=True)
class SpectralState:
    """Faithful finite-dimensional state represented by (unitary frame, log weights)."""

    log_weights: np.ndarray
    frame: np.ndarray
    label: str

    def __post_init__(self) -> None:
        lw = np.asarray(self.log_weights, dtype=float)
        u = np.asarray(self.frame, dtype=complex)
        if lw.ndim != 1:
            raise ValueError("log_weights must be one-dimensional")
        if u.shape != (len(lw), len(lw)):
            raise ValueError("frame shape does not match log_weights")
        if not np.all(np.isfinite(lw)):
            raise ValueError("faithful state requires finite log_weights")
        ident = np.eye(len(lw), dtype=complex)
        u_res = relative_fro_residual(u.conj().T @ u, ident)
        if u_res > 1e-11:
            raise ValueError(f"frame is not unitary: residual={u_res}")
        norm_res = abs(float(np.exp(lw).sum()) - 1.0)
        if norm_res > 1e-12:
            raise ValueError(f"weights are not normalized: residual={norm_res}")
        object.__setattr__(self, "log_weights", lw)
        object.__setattr__(self, "frame", u)

    @property
    def dimension(self) -> int:
        return len(self.log_weights)

    def power(self, exponent: complex) -> np.ndarray:
        """Return rho**exponent via the stored faithful spectral representation."""
        vals = np.exp(exponent * self.log_weights)
        if not np.all(np.isfinite(vals)):
            raise FloatingPointError(
                f"non-finite spectral power for {self.label}, exponent={exponent}"
            )
        return (self.frame * vals) @ self.frame.conj().T

    def density(self) -> np.ndarray:
        return self.power(1.0)

    def log_matrix(self) -> np.ndarray:
        """Return log(rho) without diagonalizing rho or clipping its spectrum."""
        return (self.frame * self.log_weights) @ self.frame.conj().T

    def expectation(self, observable: np.ndarray) -> complex:
        return complex(np.trace(self.density() @ observable))

    def diagnostics(self) -> dict[str, float | str | bool]:
        rho = self.density()
        naive = np.linalg.eigvalsh(0.5 * (rho + rho.conj().T))
        min_log = float(np.min(self.log_weights))
        min_weight = float(math.exp(min_log)) if min_log > math.log(sys.float_info.min) else 0.0
        return {
            "label": self.label,
            "dimension": self.dimension,
            "trace_residual": abs(complex(np.trace(rho)) - 1.0),
            "hermiticity_residual": relative_fro_residual(rho, rho.conj().T),
            "min_log_weight": min_log,
            "min_analytic_weight": min_weight,
            "naive_eig_min": float(np.min(naive)),
            "naive_eigendecomposition_strictly_positive": bool(np.min(naive) > 0.0),
            "below_1e_minus_15_present": bool(min_log < math.log(1e-15)),
        }


def thermal_state(n: int, beta: float, omega: float, label: str) -> SpectralState:
    return SpectralState(
        normalized_thermal_log_weights(n, beta, omega),
        np.eye(n, dtype=complex),
        label,
    )


def displaced_thermal_state(
    n: int,
    beta: float,
    omega: float,
    alpha: complex,
    label: str,
) -> SpectralState:
    return SpectralState(
        normalized_thermal_log_weights(n, beta, omega),
        displacement(n, alpha),
        label,
    )


def connes_cocycle(phi: SpectralState, psi: SpectralState, s: complex) -> np.ndarray:
    if phi.dimension != psi.dimension:
        raise ValueError("state dimensions differ")
    return phi.power(1j * s) @ psi.power(-1j * s)


def modular_flow(state: SpectralState, x: np.ndarray, s: float) -> np.ndarray:
    return state.power(1j * s) @ x @ state.power(-1j * s)


def relative_entropy(phi: SpectralState, psi: SpectralState) -> float:
    """Umegaki S(phi||psi), using floor-free stored logarithms."""
    if phi.dimension != psi.dimension:
        raise ValueError("state dimensions differ")
    rho = phi.density()
    value = np.trace(rho @ (phi.log_matrix() - psi.log_matrix()))
    if abs(value.imag) > 1e-9:
        raise FloatingPointError(f"relative entropy acquired imaginary part {value.imag}")
    return float(value.real)


def deterministic_observables(n: int) -> dict[str, np.ndarray]:
    a = annihilation(n)
    adag = a.conj().T
    x = (a + adag) / math.sqrt(2.0)
    number = adag @ a
    rng = np.random.default_rng(20260822 + n)
    raw = rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))
    hermitian = 0.5 * (raw + raw.conj().T)
    hermitian /= max(fro_norm(hermitian), 1e-300)
    return {"X": x, "N": number, "H_random": hermitian}


def state_transport_residual(
    phi: SpectralState,
    psi: SpectralState,
    observable: np.ndarray,
) -> float:
    # u_{-i/2} = rho_phi^(1/2) rho_psi^(-1/2)
    u_half = connes_cocycle(phi, psi, -0.5j)
    lhs = phi.expectation(observable)
    rhs = psi.expectation(u_half.conj().T @ observable @ u_half)
    scale = max(abs(lhs), abs(rhs), fro_norm(observable), 1.0)
    return float(abs(lhs - rhs) / scale)


def generator_residual(phi: SpectralState, psi: SpectralState, h: float = 1e-6) -> float:
    numerical = (connes_cocycle(phi, psi, h) - connes_cocycle(phi, psi, -h)) / (2.0 * h)
    analytic = 1j * (phi.log_matrix() - psi.log_matrix())
    return relative_fro_residual(numerical, analytic)


def cocycle_case(
    *,
    label: str,
    n: int,
    beta: float,
    omega: float,
    alpha: complex,
) -> dict[str, Any]:
    psi = thermal_state(n, beta, omega, f"{label}:psi_thermal")
    phi = displaced_thermal_state(n, beta, omega, alpha, f"{label}:phi_plus")
    chi = displaced_thermal_state(n, beta, omega, -0.7 * alpha, f"{label}:chi_minus")
    ident = np.eye(n, dtype=complex)

    unitarity: dict[str, float] = {}
    inverse: dict[str, float] = {}
    modular_intertwining: dict[str, float] = {}
    observables = deterministic_observables(n)
    x_probe = observables["H_random"]

    for s in S_VALUES:
        u = connes_cocycle(phi, psi, s)
        unitarity[f"{s:+.3f}"] = relative_fro_residual(u.conj().T @ u, ident)
        inverse[f"{s:+.3f}"] = relative_fro_residual(
            np.linalg.inv(u), connes_cocycle(psi, phi, s)
        )
        lhs = modular_flow(phi, x_probe, s)
        rhs = u @ modular_flow(psi, x_probe, s) @ u.conj().T
        modular_intertwining[f"{s:+.3f}"] = relative_fro_residual(lhs, rhs)

    cocycle_identity: dict[str, float] = {}
    chain_rule: dict[str, float] = {}
    for s, t in PAIR_VALUES:
        u_s = connes_cocycle(phi, psi, s)
        lhs = connes_cocycle(phi, psi, s + t)
        rhs = u_s @ modular_flow(psi, connes_cocycle(phi, psi, t), s)
        cocycle_identity[f"s={s:+.3f},t={t:+.3f}"] = relative_fro_residual(lhs, rhs)

        lhs_chain = connes_cocycle(phi, chi, s)
        rhs_chain = connes_cocycle(phi, psi, s) @ connes_cocycle(psi, chi, s)
        chain_rule[f"s={s:+.3f}"] = relative_fro_residual(lhs_chain, rhs_chain)

    transport = {
        name: state_transport_residual(phi, psi, obs)
        for name, obs in observables.items()
    }

    s_phi_psi = relative_entropy(phi, psi)
    s_psi_phi = relative_entropy(psi, phi)
    zero = relative_fro_residual(connes_cocycle(phi, psi, 0.0), ident)

    return {
        "label": label,
        "parameters": {
            "N_cut": n,
            "beta": beta,
            "omega": omega,
            "alpha_real": float(np.real(alpha)),
            "alpha_imag": float(np.imag(alpha)),
        },
        "state_diagnostics": {
            "psi": psi.diagnostics(),
            "phi": phi.diagnostics(),
            "chi": chi.diagnostics(),
        },
        "metrics": {
            "normalization_s0": zero,
            "unitarity_by_s": unitarity,
            "unitarity_max": max(unitarity.values()),
            "cocycle_identity_by_pair": cocycle_identity,
            "cocycle_identity_max": max(cocycle_identity.values()),
            "inverse_by_s": inverse,
            "inverse_max": max(inverse.values()),
            "chain_rule_by_s": chain_rule,
            "chain_rule_max": max(chain_rule.values()),
            "modular_intertwining_by_s": modular_intertwining,
            "modular_intertwining_max": max(modular_intertwining.values()),
            "state_transport_by_observable": transport,
            "state_transport_max": max(transport.values()),
            "generator_residual": generator_residual(phi, psi),
            "relative_entropy_phi_psi": s_phi_psi,
            "relative_entropy_psi_phi": s_psi_phi,
        },
    }


def source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def evaluate_gates(cases: list[dict[str, Any]]) -> dict[str, Any]:
    thresholds = {
        "normalization_s0": 2e-12,
        "unitarity_max": 2e-12,
        "cocycle_identity_max": 5e-12,
        "inverse_max": 5e-12,
        "chain_rule_max": 5e-12,
        "modular_intertwining_max": 5e-12,
        "state_transport_max": 5e-10,
        "generator_residual": 2e-8,
        "state_trace_residual": 2e-12,
        "state_hermiticity_residual": 2e-12,
        "relative_entropy_lower_bound": -5e-12,
    }

    checks: list[dict[str, Any]] = []
    for case in cases:
        m = case["metrics"]
        label = case["label"]
        for metric in (
            "normalization_s0",
            "unitarity_max",
            "cocycle_identity_max",
            "inverse_max",
            "chain_rule_max",
            "modular_intertwining_max",
            "state_transport_max",
            "generator_residual",
        ):
            value = float(m[metric])
            limit = float(thresholds[metric])
            checks.append(
                {
                    "case": label,
                    "gate": metric,
                    "value": value,
                    "limit": limit,
                    "pass": bool(value <= limit),
                }
            )

        for state_label, diag in case["state_diagnostics"].items():
            for metric, threshold_name in (
                ("trace_residual", "state_trace_residual"),
                ("hermiticity_residual", "state_hermiticity_residual"),
            ):
                value = float(diag[metric])
                limit = float(thresholds[threshold_name])
                checks.append(
                    {
                        "case": f"{label}:{state_label}",
                        "gate": metric,
                        "value": value,
                        "limit": limit,
                        "pass": bool(value <= limit),
                    }
                )

        for metric in ("relative_entropy_phi_psi", "relative_entropy_psi_phi"):
            value = float(m[metric])
            lower = float(thresholds["relative_entropy_lower_bound"])
            checks.append(
                {
                    "case": label,
                    "gate": metric,
                    "value": value,
                    "lower_bound": lower,
                    "pass": bool(value >= lower),
                }
            )

    extreme = next(c for c in cases if c["label"] == "extreme_sub_floor")
    min_log = float(extreme["state_diagnostics"]["psi"]["min_log_weight"])
    checks.append(
        {
            "case": "extreme_sub_floor",
            "gate": "contains_weight_below_1e-15",
            "value": min_log,
            "criterion": f"min_log_weight < log(1e-15)={math.log(1e-15)}",
            "pass": bool(min_log < math.log(1e-15)),
        }
    )
    checks.append(
        {
            "case": "extreme_sub_floor",
            "gate": "stress_reaches_exp_minus_300",
            "value": min_log,
            "criterion": "min_log_weight < -300",
            "pass": bool(min_log < -300.0),
        }
    )

    passed = sum(bool(c["pass"]) for c in checks)
    return {
        "thresholds": thresholds,
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "all_pass": bool(passed == len(checks)),
    }


def run() -> dict[str, Any]:
    cases = [
        cocycle_case(
            label="canonical",
            n=6,
            beta=DEFAULT_BETA,
            omega=1.0,
            alpha=0.12 + 0.03j,
        ),
        cocycle_case(
            label="detuned",
            n=8,
            beta=DEFAULT_BETA,
            omega=1.03,
            alpha=-0.09 + 0.04j,
        ),
        cocycle_case(
            label="extreme_sub_floor",
            n=16,
            beta=DEFAULT_BETA,
            omega=3.7,
            alpha=0.05 - 0.02j,
        ),
    ]
    gates = evaluate_gates(cases)
    status = (
        "PASS_FINITE_TYPE_I_COCYCLE_CONSISTENCY"
        if gates["all_pass"]
        else "FAIL_FINITE_TYPE_I_COCYCLE_CONSISTENCY"
    )
    return {
        "schema": SCHEMA,
        "metadata": {
            "numerical_algebra": "finite-dimensional Type I matrix algebra",
            "test_object": "Connes cocycle consistency for faithful spectral-frame states",
            "continuum_target": "Type III_1 -> Type II_infinity -> Type II_1",
            "continuum_claim": "NOT_TESTED",
            "clock_gate_prerequisite": "PASS_CONTINUUM_REGULATOR_SCALING",
            "state_log_policy": "NO_EIGENVALUE_FLOOR; KNOWN_SPECTRAL_FRAME_ONLY",
            "generic_matrix_log_status": "BLOCKED_WITHOUT_SUPPORT_AWARE_HIGH_PRECISION_DECOMPOSITION",
            "source_sha256": source_sha256(),
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "cases": cases,
        "gates": gates,
        "status": status,
        "next_state": (
            "READY_FOR_REGULATED_COCYCLE_READOUT_COUPLING_TEST"
            if gates["all_pass"]
            else "BLOCKED_REPAIR_FINITE_TYPE_I_COCYCLE"
        ),
        "claim_boundary": (
            "Passing certifies only the finite-Type-I algebraic/numerical cocycle identities "
            "for the tested faithful state family. It does not establish a Type-II/III "
            "crossed product, continuum Connes cocycle, or physical observer construction."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = run()
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.strict and not report["gates"]["all_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
