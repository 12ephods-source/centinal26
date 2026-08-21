#!/usr/bin/env python3
"""Finite Type-I Connes-cocycle consistency and projection-regulator harness.

This file intentionally tests only matrix-algebra identities and their interaction with
an already-validated finite GNS/clock regulator.  It does not instantiate a Type-II or
Type-III algebra and does not validate a continuum Connes Radon-Nikodym cocycle.

For faithful finite-dimensional states rho_1 and rho_0 we use

    u_s = rho_1**(i s) rho_0**(-i s)

and the modular automorphism

    sigma_s^rho(A) = rho**(i s) A rho**(-i s).

The exact finite-Type-I cocycle identity is

    u_{s+t} = u_s sigma_s^{rho_0}(u_t).

All matrix logarithms are support-aware spectral calculations.  No eigenvalue floor or
clipping is permitted.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_BETA = 2.0 * np.pi
FREQUENCIES = (1.0, 1.01, 1.03)
S_VALUES = (-0.25, -0.125, 0.0, 0.125, 0.25)
T_RATIOS = (1.0, 2.0, 4.0)
ETA_TARGETS = (0.125, 0.0625)
PERTURBATION_STRENGTHS = (0.0, 0.01, 0.03, 0.05)


@dataclass(frozen=True)
class CocycleConfig:
    n_cut: int = 6
    beta: float = DEFAULT_BETA
    q_max: float = 8.0
    sigma_ratio: float = 1.0 / 16.0
    perturbation_strength: float = 0.05
    projection_delta_q: float = 0.03125
    projection_sigma_q: float = 0.5


def hermitize(matrix: np.ndarray) -> np.ndarray:
    return 0.5 * (matrix + matrix.conj().T)


def relative_frobenius(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected, ord="fro")), 1.0e-300)
    return float(np.linalg.norm(actual - expected, ord="fro") / denominator)


def oscillator_operators(n_cut: int, omega: float) -> dict[str, np.ndarray]:
    if n_cut < 2:
        raise ValueError("n_cut must be at least 2")
    if omega <= 0.0:
        raise ValueError("omega must be positive")
    annihilation = np.zeros((n_cut, n_cut), dtype=complex)
    for n in range(1, n_cut):
        annihilation[n - 1, n] = np.sqrt(n)
    creation = annihilation.conj().T
    number = creation @ annihilation
    identity = np.eye(n_cut, dtype=complex)
    x_operator = (annihilation + creation) / np.sqrt(2.0)
    hamiltonian = omega * number
    return {
        "a": annihilation,
        "adag": creation,
        "N": number,
        "I": identity,
        "X": x_operator,
        "H": hamiltonian,
    }


def thermal_state(hamiltonian: np.ndarray, beta: float) -> np.ndarray:
    if beta <= 0.0:
        raise ValueError("beta must be positive")
    eigenvalues, unitary = np.linalg.eigh(hermitize(hamiltonian))
    shifted = eigenvalues - float(np.min(eigenvalues))
    weights = np.exp(-beta * shifted)
    partition = float(np.sum(weights))
    if not np.isfinite(partition) or partition <= 0.0:
        raise FloatingPointError("thermal partition function is invalid")
    probabilities = weights / partition
    state = (unitary * probabilities) @ unitary.conj().T
    return hermitize(state)


def density_phase(state: np.ndarray, modular_parameter: float) -> np.ndarray:
    """Return rho^(i s) using exact spectral support, with no logarithm floor."""
    values, vectors = np.linalg.eigh(hermitize(state))
    minimum = float(np.min(values))
    if minimum <= 0.0:
        raise FloatingPointError(
            f"density_phase requires a faithful state; minimum eigenvalue={minimum:.3e}"
        )
    phases = np.exp(1j * modular_parameter * np.log(values))
    result = (vectors * phases) @ vectors.conj().T
    return result


def modular_flow(state: np.ndarray, observable: np.ndarray, s: float) -> np.ndarray:
    phase = density_phase(state, s)
    return phase @ observable @ phase.conj().T


def connes_cocycle(state: np.ndarray, reference: np.ndarray, s: float) -> np.ndarray:
    return density_phase(state, s) @ density_phase(reference, -s)


def state_pair(
    *, n_cut: int, omega: float, beta: float, perturbation_strength: float
) -> dict[str, np.ndarray | float]:
    operators = oscillator_operators(n_cut, omega)
    h0 = operators["H"]
    perturbation = perturbation_strength * omega * operators["X"]
    h1 = hermitize(h0 + perturbation)
    rho0 = thermal_state(h0, beta)
    rho1 = thermal_state(h1, beta)
    return {
        **operators,
        "H1": h1,
        "rho0": rho0,
        "rho1": rho1,
        "perturbation_strength": perturbation_strength,
    }


def finite_cocycle_metrics(
    *, config: CocycleConfig, omega: float, perturbation_strength: float
) -> dict[str, Any]:
    model = state_pair(
        n_cut=config.n_cut,
        omega=omega,
        beta=config.beta,
        perturbation_strength=perturbation_strength,
    )
    rho0 = model["rho0"]
    rho1 = model["rho1"]
    identity = model["I"]
    observables = {"A_X": model["X"], "A_N": model["N"]}

    rho0_values = np.linalg.eigvalsh(rho0)
    rho1_values = np.linalg.eigvalsh(rho1)
    maximum_unitarity_residual = 0.0
    maximum_cocycle_residual = 0.0
    maximum_transport_residual = 0.0
    maximum_modular_group_residual = 0.0

    u0 = connes_cocycle(rho1, rho0, 0.0)
    u0_residual = relative_frobenius(u0, identity)

    for s in S_VALUES:
        u_s = connes_cocycle(rho1, rho0, s)
        maximum_unitarity_residual = max(
            maximum_unitarity_residual,
            relative_frobenius(u_s.conj().T @ u_s, identity),
        )
        for observable in observables.values():
            sigma1 = modular_flow(rho1, observable, s)
            transported = u_s @ modular_flow(rho0, observable, s) @ u_s.conj().T
            maximum_transport_residual = max(
                maximum_transport_residual,
                relative_frobenius(transported, sigma1),
            )

        for t in S_VALUES:
            u_t = connes_cocycle(rho1, rho0, t)
            left = connes_cocycle(rho1, rho0, s + t)
            right = u_s @ modular_flow(rho0, u_t, s)
            maximum_cocycle_residual = max(
                maximum_cocycle_residual,
                relative_frobenius(right, left),
            )
            for observable in observables.values():
                direct = modular_flow(rho1, observable, s + t)
                composed = modular_flow(rho1, modular_flow(rho1, observable, t), s)
                maximum_modular_group_residual = max(
                    maximum_modular_group_residual,
                    relative_frobenius(composed, direct),
                )

    return {
        "omega": omega,
        "perturbation_strength": perturbation_strength,
        "rho0_trace_error": float(abs(np.trace(rho0).real - 1.0)),
        "rho1_trace_error": float(abs(np.trace(rho1).real - 1.0)),
        "rho0_min_eigenvalue": float(rho0_values[0]),
        "rho1_min_eigenvalue": float(rho1_values[0]),
        "u0_identity_residual": u0_residual,
        "maximum_unitarity_residual": maximum_unitarity_residual,
        "maximum_cocycle_chain_residual": maximum_cocycle_residual,
        "maximum_state_transport_residual": maximum_transport_residual,
        "maximum_modular_group_residual": maximum_modular_group_residual,
    }


def clock_difference_classes(
    *, q_max: float, n_intervals: int
) -> tuple[np.ndarray, np.ndarray, float]:
    if q_max <= 0.0:
        raise ValueError("q_max must be positive")
    if n_intervals < 1:
        raise ValueError("n_intervals must be positive")
    delta_q = q_max / n_intervals
    offsets = np.arange(-n_intervals, n_intervals + 1, dtype=float)
    differences = offsets * delta_q
    multiplicities = (n_intervals + 1) - np.abs(offsets)
    return differences, multiplicities, delta_q


def select_resolved_intervals(
    *, q_max: float, averaging_width: float, eta_target: float
) -> int:
    """Enforce T*delta_q <= eta while avoiding all stress-frequency resonances."""
    intervals = max(1, math.ceil(q_max * averaging_width / eta_target))
    while True:
        delta_q = q_max / intervals
        offsets = [
            abs(frequency / delta_q - round(frequency / delta_q))
            for frequency in FREQUENCIES
        ]
        if all(offset > 1.0e-10 for offset in offsets):
            return intervals
        intervals += 1


def transition_entries(
    observable: np.ndarray, hamiltonian: np.ndarray, threshold: float = 1.0e-15
) -> tuple[np.ndarray, np.ndarray]:
    """Return reference-energy gaps and matrix-element weights for a left observable."""
    energies, basis = np.linalg.eigh(hermitize(hamiltonian))
    rotated = basis.conj().T @ observable @ basis
    rows, cols = np.nonzero(np.abs(rotated) > threshold)
    gaps = energies[rows] - energies[cols]
    weights = np.abs(rotated[rows, cols]) ** 2
    return gaps.real, weights.real


def filtered_norm_squared(
    *,
    observable: np.ndarray,
    hamiltonian: np.ndarray,
    config: CocycleConfig,
    t_ratio: float,
    n_intervals: int,
) -> tuple[float, float, float, bool]:
    gaps, matter_weights = transition_entries(observable, hamiltonian)
    differences, multiplicities, delta_q = clock_difference_classes(
        q_max=config.q_max, n_intervals=n_intervals
    )
    sigma_tau = config.sigma_ratio * config.beta
    averaging_width = t_ratio * config.beta
    clock_weights = multiplicities * np.exp(-(sigma_tau * differences) ** 2)
    filtered_norm2 = 0.0
    input_norm2 = 0.0
    for gap, matter_weight in zip(gaps, matter_weights, strict=True):
        constraint_difference = gap + differences
        filter_squared = np.exp(-(averaging_width * constraint_difference) ** 2)
        filtered_norm2 += float(
            matter_weight * np.sum(clock_weights * filter_squared)
        )
        input_norm2 += float(matter_weight * np.sum(clock_weights))
    exact_resonance = any(
        abs(frequency / delta_q - round(frequency / delta_q)) < 1.0e-10
        for frequency in FREQUENCIES
    )
    return filtered_norm2, input_norm2, delta_q, exact_resonance


def readout_relative_difference(
    *,
    actual: np.ndarray,
    expected: np.ndarray,
    hamiltonian: np.ndarray,
    config: CocycleConfig,
    t_ratio: float,
    n_intervals: int,
) -> float:
    difference_norm2, _, _, _ = filtered_norm_squared(
        observable=actual - expected,
        hamiltonian=hamiltonian,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    expected_norm2, _, _, _ = filtered_norm_squared(
        observable=expected,
        hamiltonian=hamiltonian,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    if expected_norm2 <= 0.0:
        raise FloatingPointError("reference readout norm vanished")
    return float(np.sqrt(max(0.0, difference_norm2) / expected_norm2))


def readout_retention(
    *,
    observable: np.ndarray,
    hamiltonian: np.ndarray,
    config: CocycleConfig,
    t_ratio: float,
    n_intervals: int,
) -> float:
    filtered, unfiltered, _, _ = filtered_norm_squared(
        observable=observable,
        hamiltonian=hamiltonian,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    if filtered <= 0.0 or unfiltered <= 0.0:
        raise FloatingPointError("readout norm vanished")
    return float(np.sqrt(filtered / unfiltered))


def cocycle_readout_metrics(
    *,
    config: CocycleConfig,
    omega: float,
    perturbation_strength: float,
    t_ratio: float,
    eta_target: float,
    s: float = 0.25,
) -> dict[str, float | int | bool]:
    model = state_pair(
        n_cut=config.n_cut,
        omega=omega,
        beta=config.beta,
        perturbation_strength=perturbation_strength,
    )
    h0 = model["H"]
    rho0 = model["rho0"]
    rho1 = model["rho1"]
    observable = model["X"]
    u_s = connes_cocycle(rho1, rho0, s)
    reference_flow = modular_flow(rho0, observable, s)
    perturbed_flow = modular_flow(rho1, observable, s)
    cocycle_transport = u_s @ reference_flow @ u_s.conj().T

    averaging_width = t_ratio * config.beta
    n_intervals = select_resolved_intervals(
        q_max=config.q_max,
        averaging_width=averaging_width,
        eta_target=eta_target,
    )
    _, _, delta_q, exact_resonance = filtered_norm_squared(
        observable=reference_flow,
        hamiltonian=h0,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    physical_mismatch = relative_frobenius(perturbed_flow, reference_flow)
    readout_mismatch = readout_relative_difference(
        actual=perturbed_flow,
        expected=reference_flow,
        hamiltonian=h0,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    readout_transport_residual = readout_relative_difference(
        actual=cocycle_transport,
        expected=perturbed_flow,
        hamiltonian=h0,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    reference_retention = readout_retention(
        observable=reference_flow,
        hamiltonian=h0,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    perturbed_retention = readout_retention(
        observable=perturbed_flow,
        hamiltonian=h0,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    return {
        "omega": omega,
        "perturbation_strength": perturbation_strength,
        "s": s,
        "T_over_beta": t_ratio,
        "eta_target": eta_target,
        "N_q": n_intervals + 1,
        "delta_q": float(delta_q),
        "T_delta_q": float(averaging_width * delta_q),
        "exact_lattice_resonance": bool(exact_resonance),
        "physical_modular_mismatch": physical_mismatch,
        "readout_modular_mismatch": readout_mismatch,
        "readout_cocycle_transport_residual": readout_transport_residual,
        "reference_observable_retention": reference_retention,
        "perturbed_observable_retention": perturbed_retention,
        "sqrt_T_ratio_scaled_reference_retention": float(
            np.sqrt(t_ratio) * reference_retention
        ),
        "sqrt_T_ratio_scaled_perturbed_retention": float(
            np.sqrt(t_ratio) * perturbed_retention
        ),
    }


def fourier_translate(psi: np.ndarray, delta_q: float, displacement: float) -> np.ndarray:
    momenta = 2.0 * np.pi * np.fft.fftfreq(psi.size, d=delta_q)
    return np.fft.ifft(np.fft.fft(psi) * np.exp(-1j * momenta * displacement))


def full_line_projection_metric(
    *, q_max: float, delta_q: float, displacement: float, sigma_q: float
) -> dict[str, float | int]:
    """Measure genuine Pi=Theta(q) leakage after a unitary full-line translation.

    The probe is a Gaussian clock-energy wavepacket on a periodic full-line regulator,
    projected onto q>=0 before translation.  The wavepacket is centered at q_max/2 so
    increasing q_max cleanly separates the support from the positivity boundary.
    """
    intervals = round((2.0 * q_max) / delta_q)
    if intervals < 8 or not math.isclose(
        intervals * delta_q, 2.0 * q_max, rel_tol=0.0, abs_tol=1.0e-12
    ):
        raise ValueError("2*q_max must be an integer multiple of delta_q")
    q_grid = -q_max + np.arange(intervals, dtype=float) * delta_q
    center = q_max / 2.0
    psi = np.exp(-((q_grid - center) ** 2) / (4.0 * sigma_q**2)).astype(complex)
    psi[q_grid < 0.0] = 0.0
    psi /= np.linalg.norm(psi)
    initial_negative_probability = float(np.sum(np.abs(psi[q_grid < 0.0]) ** 2))
    translated = fourier_translate(psi, delta_q, displacement)
    norm_error = float(abs(np.vdot(translated, translated).real - 1.0))
    negative_probability = float(
        np.sum(np.abs(translated[q_grid < 0.0]) ** 2)
    )
    projected_norm2 = float(np.sum(np.abs(translated[q_grid >= 0.0]) ** 2))
    projection_loss = float(max(0.0, 1.0 - projected_norm2))
    return {
        "q_max": q_max,
        "N_q_full_line": int(intervals),
        "delta_q": delta_q,
        "displacement": displacement,
        "initial_projection_leakage": initial_negative_probability,
        "post_translation_negative_probability": negative_probability,
        "projection_norm_loss": projection_loss,
        "translation_norm_error": norm_error,
    }


def relative_change(a: float, b: float) -> float:
    denominator = max(abs(b), 1.0e-300)
    return float(abs(a - b) / denominator)


def build_validation_payload() -> dict[str, Any]:
    config = CocycleConfig()

    algebra_scan: dict[str, Any] = {}
    for omega in FREQUENCIES:
        frequency_key = f"omega_{omega:.2f}"
        algebra_scan[frequency_key] = {}
        for perturbation_strength in PERTURBATION_STRENGTHS:
            algebra_scan[frequency_key][
                f"kappa_{perturbation_strength:.2f}"
            ] = finite_cocycle_metrics(
                config=config,
                omega=omega,
                perturbation_strength=perturbation_strength,
            )

    readout_scan: dict[str, Any] = {}
    readout_index: dict[tuple[float, float, float], dict[str, Any]] = {}
    for omega in FREQUENCIES:
        frequency_key = f"omega_{omega:.2f}"
        readout_scan[frequency_key] = {}
        for t_ratio in T_RATIOS:
            t_key = f"T_over_beta_{t_ratio:g}"
            readout_scan[frequency_key][t_key] = {}
            for eta_target in ETA_TARGETS:
                metric = cocycle_readout_metrics(
                    config=config,
                    omega=omega,
                    perturbation_strength=config.perturbation_strength,
                    t_ratio=t_ratio,
                    eta_target=eta_target,
                )
                readout_scan[frequency_key][t_key][
                    f"eta_target_{eta_target:g}"
                ] = metric
                readout_index[(omega, t_ratio, eta_target)] = metric

    zero_control = cocycle_readout_metrics(
        config=config,
        omega=1.03,
        perturbation_strength=0.0,
        t_ratio=2.0,
        eta_target=min(ETA_TARGETS),
    )

    projection_scan: dict[str, Any] = {}
    projection_metrics = []
    for q_max in (4.0, 6.0, 8.0, 10.0):
        metric = full_line_projection_metric(
            q_max=q_max,
            delta_q=config.projection_delta_q,
            displacement=-max(FREQUENCIES),
            sigma_q=config.projection_sigma_q,
        )
        projection_scan[f"q_max_{q_max:g}"] = metric
        projection_metrics.append(metric)

    algebra_metrics = [
        algebra_scan[f"omega_{omega:.2f}"][f"kappa_{config.perturbation_strength:.2f}"]
        for omega in FREQUENCIES
    ]
    maximum_unitarity = max(float(item["maximum_unitarity_residual"]) for item in algebra_metrics)
    maximum_chain = max(float(item["maximum_cocycle_chain_residual"]) for item in algebra_metrics)
    maximum_transport = max(float(item["maximum_state_transport_residual"]) for item in algebra_metrics)
    maximum_group = max(float(item["maximum_modular_group_residual"]) for item in algebra_metrics)
    minimum_support = min(
        min(float(item["rho0_min_eigenvalue"]), float(item["rho1_min_eigenvalue"]))
        for item in algebra_metrics
    )

    refinement_changes = []
    maximum_readout_transport = 0.0
    minimum_nontrivial_physical_mismatch = math.inf
    minimum_nontrivial_readout_mismatch = math.inf
    minimum_retention = math.inf
    any_resonance = False
    for omega in FREQUENCIES:
        for t_ratio in T_RATIOS:
            coarse = readout_index[(omega, t_ratio, max(ETA_TARGETS))]
            fine = readout_index[(omega, t_ratio, min(ETA_TARGETS))]
            for field in (
                "readout_modular_mismatch",
                "reference_observable_retention",
                "perturbed_observable_retention",
            ):
                refinement_changes.append(
                    relative_change(float(coarse[field]), float(fine[field]))
                )
            maximum_readout_transport = max(
                maximum_readout_transport,
                float(fine["readout_cocycle_transport_residual"]),
            )
            minimum_nontrivial_physical_mismatch = min(
                minimum_nontrivial_physical_mismatch,
                float(fine["physical_modular_mismatch"]),
            )
            minimum_nontrivial_readout_mismatch = min(
                minimum_nontrivial_readout_mismatch,
                float(fine["readout_modular_mismatch"]),
            )
            minimum_retention = min(
                minimum_retention,
                float(fine["reference_observable_retention"]),
                float(fine["perturbed_observable_retention"]),
            )
            any_resonance = any_resonance or bool(fine["exact_lattice_resonance"])

    maximum_refinement_change = max(refinement_changes)
    projection_leakages = [
        float(item["post_translation_negative_probability"])
        for item in projection_metrics
    ]
    projection_norm_error = max(
        float(item["translation_norm_error"]) for item in projection_metrics
    )
    projection_decay_ratio = projection_leakages[-1] / max(projection_leakages[0], 1.0e-300)

    thresholds = {
        "finite_matrix_identity_residual_max": 1.0e-11,
        "readout_transport_residual_max": 1.0e-10,
        "zero_perturbation_mismatch_max": 1.0e-11,
        "nontrivial_physical_mismatch_min": 1.0e-4,
        "nontrivial_readout_mismatch_min": 1.0e-5,
        "eta_refinement_relative_change_max": 2.0e-2,
        "minimum_observable_retention": 1.0e-4,
        "projection_translation_norm_error_max": 1.0e-12,
        "projection_cutoff_decay_ratio_max": 1.0e-4,
        "projection_coarse_leakage_min": 1.0e-6,
    }
    gates = {
        "faithful_density_support": minimum_support > 0.0,
        "cocycle_unitarity": maximum_unitarity
        <= thresholds["finite_matrix_identity_residual_max"],
        "cocycle_chain_rule": maximum_chain
        <= thresholds["finite_matrix_identity_residual_max"],
        "state_transport_identity": maximum_transport
        <= thresholds["finite_matrix_identity_residual_max"],
        "modular_group_identity": maximum_group
        <= thresholds["finite_matrix_identity_residual_max"],
        "zero_perturbation_control": max(
            float(zero_control["physical_modular_mismatch"]),
            float(zero_control["readout_modular_mismatch"]),
        )
        <= thresholds["zero_perturbation_mismatch_max"],
        "nontrivial_state_mismatch": minimum_nontrivial_physical_mismatch
        >= thresholds["nontrivial_physical_mismatch_min"],
        "nontrivial_readout_mismatch": minimum_nontrivial_readout_mismatch
        >= thresholds["nontrivial_readout_mismatch_min"],
        "readout_cocycle_transport": maximum_readout_transport
        <= thresholds["readout_transport_residual_max"],
        "resolved_eta_refinement": maximum_refinement_change
        <= thresholds["eta_refinement_relative_change_max"],
        "nontrivial_retention": minimum_retention
        >= thresholds["minimum_observable_retention"],
        "detuned_nonresonant_regulator": not any_resonance,
        "full_line_projection_unitarity": projection_norm_error
        <= thresholds["projection_translation_norm_error_max"],
        "full_line_projection_is_nontrivial": projection_leakages[0]
        >= thresholds["projection_coarse_leakage_min"],
        "full_line_projection_cutoff_decay": projection_decay_ratio
        <= thresholds["projection_cutoff_decay_ratio_max"],
    }
    overall_pass = all(gates.values())

    source_path = Path(__file__).resolve()
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    config_json = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return {
        "metadata": {
            "schema_version": 1,
            "numerical_algebra": "finite-dimensional Type I matrix algebra with GNS-clock regulator",
            "continuum_target": "Type III_1 -> Type II_infinity -> Type II_1",
            "cocycle_definition": "u_s = rho_1^(i s) rho_0^(-i s)",
            "modular_flow_definition": "sigma_s^rho(A) = rho^(i s) A rho^(-i s)",
            "classification": "EXPERIMENTAL",
            "support_aware_logarithm": True,
            "logarithm_eigenvalue_floor": None,
            "finite_type_i_cocycle_status": (
                "PASS_FINITE_TYPE_I_COCYCLE_CONSISTENCY"
                if overall_pass
                else "FAIL_FINITE_TYPE_I_COCYCLE_CONSISTENCY"
            ),
            "continuum_connes_cocycle_status": "BLOCKED_NOT_ESTABLISHED_BY_FINITE_MATRICES",
            "generated_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "platform": platform.platform(),
            "source_sha256": source_sha256,
            "configuration_sha256": hashlib.sha256(config_json.encode()).hexdigest(),
        },
        "fixed_parameters": asdict(config),
        "finite_matrix_cocycle_scan": algebra_scan,
        "resolved_clock_readout_scan": readout_scan,
        "zero_perturbation_control": zero_control,
        "full_line_projection_scan": projection_scan,
        "validation_summary": {
            "minimum_density_eigenvalue": minimum_support,
            "maximum_cocycle_unitarity_residual": maximum_unitarity,
            "maximum_cocycle_chain_residual": maximum_chain,
            "maximum_state_transport_residual": maximum_transport,
            "maximum_modular_group_residual": maximum_group,
            "maximum_readout_cocycle_transport_residual": maximum_readout_transport,
            "minimum_nontrivial_physical_modular_mismatch": minimum_nontrivial_physical_mismatch,
            "minimum_nontrivial_readout_modular_mismatch": minimum_nontrivial_readout_mismatch,
            "maximum_eta_refinement_relative_change": maximum_refinement_change,
            "minimum_observable_retention": minimum_retention,
            "maximum_projection_translation_norm_error": projection_norm_error,
            "projection_leakage_qmax4": projection_leakages[0],
            "projection_leakage_qmax10": projection_leakages[-1],
            "projection_leakage_decay_ratio": projection_decay_ratio,
            "thresholds": thresholds,
            "gates": gates,
            "overall_status": (
                "PASS_FINITE_TYPE_I_COCYCLE_CONSISTENCY"
                if overall_pass
                else "FAIL_FINITE_TYPE_I_COCYCLE_CONSISTENCY"
            ),
        },
        "interpretation_limits": [
            "The cocycle identity is exact in every faithful finite matrix algebra and is therefore a consistency test, not evidence for a continuum Type-III factor.",
            "The same reference static-patch Hamiltonian defines the finite clock constraint used for the regulated readout scan.",
            "The nonzero modular mismatch compares the perturbed-state and reference-state modular flows; it is not by itself a physical observable prediction.",
            "The full-line projection probe tests an actual Pi=Theta(q) compression route using a localized clock-energy wavepacket; it is separate from the positive-grid POVM implementation.",
            "Passing this harness can authorize construction of a continuum-motivated cocycle approximation only as a new, separately gated hypothesis.",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit nonzero unless every finite-Type-I validation gate passes",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_validation_payload()
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.strict and payload["validation_summary"]["overall_status"] != "PASS_FINITE_TYPE_I_COCYCLE_CONSISTENCY":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
