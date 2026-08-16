#!/usr/bin/env python3
"""Finite Type-I GNS/clock regulator convergence harness.

The implementation evaluates Frobenius residuals exactly, while compressing the
uniform clock grid by energy-difference multiplicity.  No target residual is
hardcoded.  A small dense construction independently cross-checks the compressed
calculation and the matter/clock intertwining signs.
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
DEFAULT_SIGMA_RATIO = 1.0 / 16.0
DEFAULT_MODULAR_PARAMETER = 0.25
FREQUENCIES = (1.0, 1.01, 1.03)
T_RATIOS = (0.5, 1.0, 2.0, 4.0, 8.0)
ETA_TARGETS = (0.25, 0.125, 0.0625)


@dataclass(frozen=True)
class HarnessConfig:
    n_cut: int = 6
    beta: float = DEFAULT_BETA
    q_max: float = 8.0
    sigma_ratio: float = DEFAULT_SIGMA_RATIO
    modular_parameter: float = DEFAULT_MODULAR_PARAMETER


def oscillator_matrices(n_cut: int, omega: float) -> tuple[np.ndarray, ...]:
    """Construct the truncated oscillator, GNS Liouvillian, and controls."""
    if n_cut < 2:
        raise ValueError("n_cut must be at least 2")
    if omega <= 0.0:
        raise ValueError("omega must be positive")

    annihilation = np.zeros((n_cut, n_cut), dtype=complex)
    for n in range(1, n_cut):
        annihilation[n - 1, n] = np.sqrt(n)
    creation = annihilation.conj().T
    number = creation @ annihilation
    hamiltonian = omega * number
    identity = np.eye(n_cut, dtype=complex)
    liouvillian = np.kron(hamiltonian, identity) - np.kron(
        identity, hamiltonian.T
    )
    a_x = np.kron((annihilation + creation) / np.sqrt(2.0), identity)
    a_n = np.kron(number, identity)
    return annihilation, hamiltonian, liouvillian, a_x, a_n


def transition_data(
    n_cut: int,
    omega: float,
    observable: str = "A_X",
    threshold: float = 1.0e-14,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Rotate an observable into the diagonal Liouvillian basis.

    Returns Liouvillian gaps, squared matrix-element magnitudes, and the
    diagonalization-unitarity residual.
    """
    _, _, liouvillian, a_x, a_n = oscillator_matrices(n_cut, omega)
    eigenvalues, unitary = np.linalg.eigh(liouvillian)
    selected = {"A_X": a_x, "A_N": a_n}.get(observable)
    if selected is None:
        raise ValueError(f"unsupported observable: {observable}")
    rotated = unitary.conj().T @ selected @ unitary
    rows, cols = np.nonzero(np.abs(rotated) > threshold)
    gaps = eigenvalues[rows] - eigenvalues[cols]
    weights = np.abs(rotated[rows, cols]) ** 2
    identity = np.eye(unitary.shape[0], dtype=complex)
    unitarity_residual = float(np.linalg.norm(unitary.conj().T @ unitary - identity))
    return gaps.real, weights.real, unitarity_residual


def clock_difference_classes(
    *, q_max: float, n_intervals: int
) -> tuple[np.ndarray, np.ndarray, float]:
    """Return every clock-energy difference and its exact pair multiplicity."""
    if q_max <= 0.0:
        raise ValueError("q_max must be positive")
    if n_intervals < 1:
        raise ValueError("n_intervals must be positive")
    delta_q = q_max / n_intervals
    offsets = np.arange(-n_intervals, n_intervals + 1, dtype=float)
    differences = offsets * delta_q
    multiplicities = (n_intervals + 1) - np.abs(offsets)
    return differences, multiplicities, delta_q


def intervals_for_delta(q_max: float, delta_q: float) -> int:
    """Require a uniform grid whose final point is exactly q_max."""
    if delta_q <= 0.0:
        raise ValueError("delta_q must be positive")
    intervals = round(q_max / delta_q)
    if not math.isclose(intervals * delta_q, q_max, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError("q_max must be an integer multiple of delta_q")
    return intervals


def select_resolved_intervals(
    *,
    q_max: float,
    averaging_width: float,
    eta_target: float,
    frequencies: tuple[float, ...] = FREQUENCIES,
    resonance_tolerance: float = 1.0e-10,
) -> int:
    """Choose T*delta_q <= eta_target while avoiding exact lattice locking."""
    if averaging_width <= 0.0 or eta_target <= 0.0:
        raise ValueError("averaging_width and eta_target must be positive")
    intervals = max(1, math.ceil(q_max * averaging_width / eta_target))
    while True:
        delta_q = q_max / intervals
        offsets = [abs(freq / delta_q - round(freq / delta_q)) for freq in frequencies]
        if all(offset > resonance_tolerance for offset in offsets):
            return intervals
        intervals += 1


def continuum_predictions(
    *, averaging_width: float, beta: float, modular_parameter: float, omega: float
) -> dict[str, float]:
    """Large-q_max continuum predictions for the Gaussian difference filter."""
    r_c = 1.0 / (np.sqrt(2.0) * averaging_width * omega)
    modular_shift = beta * modular_parameter
    r_int_squared = 2.0 * (
        1.0 - np.exp(-(modular_shift**2) / (4.0 * averaging_width**2))
    )
    return {
        "R_C_over_omega": float(r_c),
        "R_int_corrected": float(np.sqrt(max(0.0, r_int_squared))),
    }


def relational_metrics(
    *,
    config: HarnessConfig,
    omega: float,
    t_ratio: float,
    n_intervals: int,
) -> dict[str, float | int | bool]:
    """Evaluate exact Frobenius sums without allocating the full tensor matrix."""
    if t_ratio <= 0.0:
        raise ValueError("t_ratio must be positive")
    gaps, matter_weights, unitary_residual = transition_data(config.n_cut, omega)
    differences, multiplicities, delta_q = clock_difference_classes(
        q_max=config.q_max, n_intervals=n_intervals
    )
    sigma_tau = config.sigma_ratio * config.beta
    averaging_width = t_ratio * config.beta

    # |E_{jk}|^2 contributes exp(-sigma_tau^2 * (q_j-q_k)^2).
    # The common factor 1/P^2 cancels from every normalized metric.
    clock_weights = multiplicities * np.exp(-(sigma_tau * differences) ** 2)
    filtered_norm2 = 0.0
    input_norm2 = 0.0
    commutator_norm2 = 0.0
    intertwining_difference_norm2 = 0.0

    for gap, matter_weight in zip(gaps, matter_weights, strict=True):
        constraint_difference = gap + differences
        kernel_squared = np.exp(-(averaging_width * constraint_difference) ** 2)
        weights = matter_weight * clock_weights * kernel_squared
        filtered_norm2 += float(np.sum(weights))
        input_norm2 += float(matter_weight * np.sum(clock_weights))
        commutator_norm2 += float(np.sum(weights * constraint_difference**2))

        # Exact phase difference between alpha_{-beta*s}(A) and E_{tau-beta*s}.
        phase_difference_squared = 4.0 * np.sin(
            0.5 * config.beta * config.modular_parameter * constraint_difference
        ) ** 2
        intertwining_difference_norm2 += float(
            np.sum(weights * phase_difference_squared)
        )

    if filtered_norm2 <= 0.0 or input_norm2 <= 0.0:
        raise FloatingPointError("relational readout norm underflowed to zero")

    r_c = np.sqrt(commutator_norm2 / filtered_norm2) / omega
    r_int = np.sqrt(intertwining_difference_norm2 / filtered_norm2)
    retention = np.sqrt(filtered_norm2 / input_norm2)
    prediction = continuum_predictions(
        averaging_width=averaging_width,
        beta=config.beta,
        modular_parameter=config.modular_parameter,
        omega=omega,
    )
    commensurability_offset = abs(omega / delta_q - round(omega / delta_q))
    return {
        "N_q": n_intervals + 1,
        "delta_q": float(delta_q),
        "T_delta_q": float(averaging_width * delta_q),
        "commensurability_offset": float(commensurability_offset),
        "exact_lattice_resonance": bool(commensurability_offset < 1.0e-10),
        "R_C_over_omega": float(r_c),
        "R_int_corrected": float(r_int),
        "observable_retention": float(retention),
        "sqrt_T_ratio_scaled_retention": float(np.sqrt(t_ratio) * retention),
        "continuum_R_C_over_omega": prediction["R_C_over_omega"],
        "continuum_R_int_corrected": prediction["R_int_corrected"],
        "R_C_relative_error": float(
            abs(r_c - prediction["R_C_over_omega"])
            / prediction["R_C_over_omega"]
        ),
        "R_int_relative_error": float(
            abs(r_int - prediction["R_int_corrected"])
            / prediction["R_int_corrected"]
        ),
        "liouvillian_basis_unitarity_residual": unitary_residual,
    }


def time_povm_metrics(
    *, q_max: float, delta_q: float, sigma_tau: float, tau: float | None = None
) -> dict[str, float | int]:
    """Directly verify endpoint-free finite-DFT resolution and POVM positivity."""
    n_intervals = intervals_for_delta(q_max, delta_q)
    q_grid = np.arange(n_intervals + 1, dtype=float) * delta_q
    n_q = q_grid.size
    period = 2.0 * np.pi / delta_q
    tau_value = period / 2.0 if tau is None else tau % period
    difference = q_grid[:, None] - q_grid[None, :]
    gaussian = np.exp(-0.5 * (sigma_tau * difference) ** 2)

    e_tau = (
        np.exp(-1j * difference * tau_value) * gaussian / period
    )
    eigenvalues = np.linalg.eigvalsh(e_tau)

    n_tau = 2 * n_q
    tau_grid = np.arange(n_tau, dtype=float) * (period / n_tau)
    phase_average = np.exp(-1j * difference[..., None] * tau_grid).mean(axis=-1)
    integrated = gaussian * phase_average
    residual = np.linalg.norm(integrated - np.eye(n_q), ord="fro")
    return {
        "N_q": int(n_q),
        "N_tau": int(n_tau),
        "P_recurrence": float(period),
        "R_POVM": float(residual),
        "lambda_min_E": float(eigenvalues[0]),
    }


def dense_crosscheck() -> dict[str, float | dict[str, float | int | bool]]:
    """Cross-check compressed sums against explicit finite matrices."""
    config = HarnessConfig(n_cut=4, q_max=4.0)
    omega = 1.03
    t_ratio = 1.0
    delta_q = 0.5
    n_intervals = intervals_for_delta(config.q_max, delta_q)
    compressed = relational_metrics(
        config=config,
        omega=omega,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )

    _, _, liouvillian, a_x, a_n = oscillator_matrices(config.n_cut, omega)
    l_values, unitary = np.linalg.eigh(liouvillian)
    a_x_rotated = unitary.conj().T @ a_x @ unitary
    a_n_rotated = unitary.conj().T @ a_n @ unitary
    q_grid = np.arange(n_intervals + 1, dtype=float) * delta_q
    n_q = q_grid.size
    period = 2.0 * np.pi / delta_q
    tau = period / 2.0
    difference = q_grid[:, None] - q_grid[None, :]
    sigma_tau = config.sigma_ratio * config.beta
    e_tau = (
        np.exp(-1j * difference * tau)
        * np.exp(-0.5 * (sigma_tau * difference) ** 2)
        / period
    )
    constraint_values = np.repeat(l_values, n_q) + np.tile(q_grid, l_values.size)
    constraint_difference = constraint_values[:, None] - constraint_values[None, :]
    averaging_width = t_ratio * config.beta
    kernel = np.exp(-0.5 * (averaging_width * constraint_difference) ** 2)

    def readout(observable: np.ndarray, clock_effect: np.ndarray) -> np.ndarray:
        return np.kron(observable, clock_effect) * kernel

    x_total = np.kron(a_x_rotated, e_tau)
    r_ax = x_total * kernel
    r_c = (
        np.linalg.norm(constraint_difference * r_ax, ord="fro")
        / np.linalg.norm(r_ax, ord="fro")
        / omega
    )
    retention = np.linalg.norm(r_ax, ord="fro") / np.linalg.norm(x_total, ord="fro")

    matter_phases = np.exp(-1j * config.beta * config.modular_parameter * l_values)
    flowed = matter_phases[:, None] * a_x_rotated * matter_phases.conj()[None, :]
    left = readout(flowed, e_tau)
    shifted_tau = (tau - config.beta * config.modular_parameter) % period
    shifted_effect = (
        np.exp(-1j * difference * shifted_tau)
        * np.exp(-0.5 * (sigma_tau * difference) ** 2)
        / period
    )
    right = readout(a_x_rotated, shifted_effect)
    r_int = np.linalg.norm(left - right, ord="fro") / np.linalg.norm(left, ord="fro")

    r_ax_dagger = readout(a_x_rotated.conj().T, e_tau)
    r_an = readout(a_n_rotated, e_tau)
    r_an_dagger = readout(a_n_rotated.conj().T, e_tau)
    r_star_ax = np.linalg.norm(r_ax_dagger - r_ax.conj().T, ord="fro") / np.linalg.norm(
        r_ax, ord="fro"
    )
    r_star_an = np.linalg.norm(r_an_dagger - r_an.conj().T, ord="fro") / np.linalg.norm(
        r_an, ord="fro"
    )

    discrepancies = {
        "R_C_absolute_difference": float(abs(r_c - compressed["R_C_over_omega"])),
        "R_int_absolute_difference": float(
            abs(r_int - compressed["R_int_corrected"])
        ),
        "retention_absolute_difference": float(
            abs(retention - compressed["observable_retention"])
        ),
    }
    return {
        "configuration": {
            "N_cut": config.n_cut,
            "omega": omega,
            "q_max": config.q_max,
            "delta_q": delta_q,
            "T_over_beta": t_ratio,
        },
        "dense_metrics": {
            "R_C_over_omega": float(r_c),
            "R_int_corrected": float(r_int),
            "observable_retention": float(retention),
            "R_star_A_X": float(r_star_ax),
            "R_star_A_N": float(r_star_an),
        },
        "compressed_metrics": compressed,
        "discrepancies": discrepancies,
        "maximum_absolute_discrepancy": max(discrepancies.values()),
    }


def relative_span(values: list[float]) -> float:
    mean = float(np.mean(values))
    if mean == 0.0:
        return math.inf
    return float((max(values) - min(values)) / abs(mean))


def build_validation_payload() -> dict[str, Any]:
    config = HarnessConfig()
    baseline_intervals = intervals_for_delta(config.q_max, 0.25)
    half_intervals = intervals_for_delta(config.q_max, 0.125)
    locked_base = relational_metrics(
        config=config, omega=1.0, t_ratio=2.0, n_intervals=baseline_intervals
    )
    fixed_delta_half = relational_metrics(
        config=config, omega=1.0, t_ratio=2.0, n_intervals=half_intervals
    )
    povm = time_povm_metrics(
        q_max=config.q_max,
        delta_q=0.25,
        sigma_tau=config.sigma_ratio * config.beta,
    )
    dense = dense_crosscheck()

    fixed_grid_scan: dict[str, dict[str, dict[str, float | int | bool]]] = {}
    for omega in FREQUENCIES:
        frequency_key = f"omega_{omega:.2f}"
        fixed_grid_scan[frequency_key] = {}
        for t_ratio in T_RATIOS:
            fixed_grid_scan[frequency_key][f"T_over_beta_{t_ratio:g}"] = (
                relational_metrics(
                    config=config,
                    omega=omega,
                    t_ratio=t_ratio,
                    n_intervals=baseline_intervals,
                )
            )

    paired_scan: dict[str, dict[str, dict[str, dict[str, float | int | bool]]]] = {}
    paired_index: dict[tuple[float, float, float], dict[str, float | int | bool]] = {}
    for eta_target in ETA_TARGETS:
        eta_key = f"eta_target_{eta_target:g}"
        paired_scan[eta_key] = {}
        for omega in FREQUENCIES:
            frequency_key = f"omega_{omega:.2f}"
            paired_scan[eta_key][frequency_key] = {}
            for t_ratio in T_RATIOS:
                averaging_width = t_ratio * config.beta
                n_intervals = select_resolved_intervals(
                    q_max=config.q_max,
                    averaging_width=averaging_width,
                    eta_target=eta_target,
                )
                metric = relational_metrics(
                    config=config,
                    omega=omega,
                    t_ratio=t_ratio,
                    n_intervals=n_intervals,
                )
                paired_scan[eta_key][frequency_key][
                    f"T_over_beta_{t_ratio:g}"
                ] = metric
                paired_index[(eta_target, omega, t_ratio)] = metric

    q_max_scan: dict[str, dict[str, float | int | bool]] = {}
    q_max_metrics: list[dict[str, float | int | bool]] = []
    for q_max in (4.0, 6.0, 8.0, 10.0):
        q_config = HarnessConfig(q_max=q_max)
        t_ratio = 2.0
        n_intervals = select_resolved_intervals(
            q_max=q_max,
            averaging_width=t_ratio * q_config.beta,
            eta_target=0.125,
        )
        metric = relational_metrics(
            config=q_config,
            omega=1.0,
            t_ratio=t_ratio,
            n_intervals=n_intervals,
        )
        q_max_scan[f"q_max_{q_max:g}"] = metric
        q_max_metrics.append(metric)

    finest_eta = min(ETA_TARGETS)
    finest_metrics = [
        paired_index[(finest_eta, omega, t_ratio)]
        for omega in FREQUENCIES
        for t_ratio in T_RATIOS
    ]
    maximum_continuum_r_c_error = max(
        float(metric["R_C_relative_error"]) for metric in finest_metrics
    )
    maximum_continuum_r_int_error = max(
        float(metric["R_int_relative_error"]) for metric in finest_metrics
    )

    refinement_changes: list[float] = []
    for omega in FREQUENCIES:
        for t_ratio in T_RATIOS:
            medium = paired_index[(0.125, omega, t_ratio)]
            fine = paired_index[(0.0625, omega, t_ratio)]
            for field in ("R_C_over_omega", "R_int_corrected", "observable_retention"):
                denominator = abs(float(fine[field]))
                refinement_changes.append(
                    abs(float(medium[field]) - float(fine[field])) / denominator
                )
    maximum_refinement_change = max(refinement_changes)

    retention_spans = []
    for omega in FREQUENCIES:
        retention_spans.append(
            relative_span(
                [
                    float(
                        paired_index[(finest_eta, omega, t_ratio)][
                            "sqrt_T_ratio_scaled_retention"
                        ]
                    )
                    for t_ratio in T_RATIOS
                ]
            )
        )
    maximum_scaled_retention_span = max(retention_spans)
    q_max_r_c_span = relative_span(
        [float(metric["R_C_over_omega"]) for metric in q_max_metrics]
    )
    q_max_r_int_span = relative_span(
        [float(metric["R_int_corrected"]) for metric in q_max_metrics]
    )

    coarse_t4 = fixed_grid_scan["omega_1.00"]["T_over_beta_4"]
    resolved_t4 = paired_index[(finest_eta, 1.0, 4.0)]
    locking_ratio = float(coarse_t4["R_C_over_omega"]) / float(
        resolved_t4["R_C_over_omega"]
    )
    detuned_coarse_t4 = fixed_grid_scan["omega_1.01"]["T_over_beta_4"]
    lattice_lock_detected = bool(
        coarse_t4["exact_lattice_resonance"]
        and locking_ratio < 1.0e-5
        and float(detuned_coarse_t4["R_C_over_omega"]) > 1.0e-3
    )

    thresholds = {
        "R_POVM_max": 1.0e-12,
        "dense_compressed_max_absolute_difference": 1.0e-12,
        "continuum_relative_error_max": 1.0e-2,
        "eta_refinement_relative_change_max": 2.0e-3,
        "scaled_retention_relative_span_max": 1.0e-2,
        "q_max_residual_relative_span_max": 1.0e-3,
    }
    gates = {
        "endpoint_free_POVM": povm["R_POVM"] <= thresholds["R_POVM_max"],
        "dense_compressed_agreement": dense["maximum_absolute_discrepancy"]
        <= thresholds["dense_compressed_max_absolute_difference"],
        "continuum_R_C_scaling": maximum_continuum_r_c_error
        <= thresholds["continuum_relative_error_max"],
        "continuum_R_int_scaling": maximum_continuum_r_int_error
        <= thresholds["continuum_relative_error_max"],
        "eta_refinement_stability": maximum_refinement_change
        <= thresholds["eta_refinement_relative_change_max"],
        "scaled_retention_stability": maximum_scaled_retention_span
        <= thresholds["scaled_retention_relative_span_max"],
        "q_max_residual_stability": max(q_max_r_c_span, q_max_r_int_span)
        <= thresholds["q_max_residual_relative_span_max"],
        "coarse_grid_false_positive_detected": lattice_lock_detected,
    }
    overall_pass = all(gates.values())

    source_path = Path(__file__).resolve()
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    config_json = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return {
        "metadata": {
            "schema_version": 1,
            "numerical_algebra": "finite-dimensional Type I GNS-clock regulator",
            "continuum_target": "Type III_1 -> Type II_infinity -> Type II_1",
            "map_under_test": "regulated relational readout; not a proven embedding",
            "evaluation_algorithm": (
                "exact Frobenius sums compressed by uniform-grid difference multiplicity"
            ),
            "classification": "EXPERIMENTAL",
            "connes_cocycle_status": (
                "READY_FOR_FINITE_TYPE_I_COCYCLE_TEST"
                if overall_pass
                else "BLOCKED_PENDING_CLOCK_SCALING"
            ),
            "continuum_cocycle_physics_validated": False,
            "generated_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "platform": platform.platform(),
            "source_sha256": source_sha256,
            "configuration_sha256": hashlib.sha256(config_json.encode()).hexdigest(),
        },
        "fixed_parameters": asdict(config),
        "baseline": {
            "locked_delta_q_0.25": locked_base,
            "fixed_T_delta_q_half": fixed_delta_half,
            "povm": povm,
            "dense_matrix_crosscheck": dense,
        },
        "fixed_delta_q_scan": fixed_grid_scan,
        "coupled_T_delta_q_scan": paired_scan,
        "resolved_q_max_scan": q_max_scan,
        "validation_summary": {
            "maximum_continuum_R_C_relative_error": maximum_continuum_r_c_error,
            "maximum_continuum_R_int_relative_error": maximum_continuum_r_int_error,
            "maximum_eta_refinement_relative_change": maximum_refinement_change,
            "maximum_scaled_retention_relative_span": maximum_scaled_retention_span,
            "q_max_R_C_relative_span": q_max_r_c_span,
            "q_max_R_int_relative_span": q_max_r_int_span,
            "coarse_to_resolved_R_C_ratio_at_T_over_beta_4": locking_ratio,
            "lattice_lock_false_positive_detected": lattice_lock_detected,
            "thresholds": thresholds,
            "gates": gates,
            "overall_status": (
                "PASS_CONTINUUM_REGULATOR_SCALING"
                if overall_pass
                else "FAIL_CONTINUUM_REGULATOR_SCALING"
            ),
        },
        "interpretation_limits": [
            "The finite matrix algebra is Type I; it does not instantiate a Type II or III factor.",
            (
                "Small fixed-grid residuals at exact arithmetic resonance are "
                "lattice-locking artifacts."
            ),
            (
                "Raw Frobenius retention decays as T grows; sqrt(T/beta)-scaled "
                "retention is the stable diagnostic."
            ),
            "Passing these gates authorizes only a finite-Type-I cocycle consistency test.",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="write the complete JSON report to this path (stdout if omitted)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit nonzero unless every validation gate passes",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_validation_payload()
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        summary = payload["validation_summary"]
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "overall_status": summary["overall_status"],
                    "gates": summary["gates"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(encoded, end="")
    if args.strict and payload["validation_summary"]["overall_status"].startswith("FAIL"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
