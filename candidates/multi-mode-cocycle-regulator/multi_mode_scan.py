"""Bounded 2-4 mode finite Type-I cocycle/regulator stress test.

This is a finite-dimensional numerical stress test downstream of the validated
single- and two-mode cocycle gates. It is not a field algebra or continuum
Connes-cocycle construction.
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

BETA = 2.0 * np.pi
S_VALUES = (-0.25, -0.125, 0.0, 0.125, 0.25)
MODE_COUNTS = (2, 3, 4)
BASE_FREQUENCIES = (1.00, 1.37, 1.73, 2.11)
ETA_TARGETS = (0.125, 0.0625)
T_RATIOS = (2.0, 4.0)


@dataclass(frozen=True)
class Config:
    n_cut_per_mode: int = 2
    beta: float = BETA
    q_max: float = 8.0
    sigma_ratio: float = 1.0 / 16.0
    local_perturbation_strength: float = 0.04
    nearest_neighbor_coupling: float = 0.02


def hermitize(a: np.ndarray) -> np.ndarray:
    return (a + a.conj().T) / 2.0


def relative_frobenius(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / max(np.linalg.norm(b), 1.0e-300))


def positive_power(rho: np.ndarray, exponent: complex) -> np.ndarray:
    values, basis = np.linalg.eigh(hermitize(rho))
    if float(values.min()) <= 0.0:
        raise FloatingPointError("density matrix lost faithful support")
    return (basis * (values.astype(complex) ** exponent)) @ basis.conj().T


def thermal_state(hamiltonian: np.ndarray, beta: float) -> np.ndarray:
    energies, basis = np.linalg.eigh(hermitize(hamiltonian))
    weights = np.exp(-beta * (energies - energies.min()))
    rho = (basis * weights) @ basis.conj().T
    return hermitize(rho / np.trace(rho))


def cocycle(rho1: np.ndarray, rho0: np.ndarray, s: float) -> np.ndarray:
    return positive_power(rho1, 1j * s) @ positive_power(rho0, -1j * s)


def modular_flow(rho: np.ndarray, observable: np.ndarray, s: float) -> np.ndarray:
    return positive_power(rho, 1j * s) @ observable @ positive_power(rho, -1j * s)


def local_operator(operator: np.ndarray, site: int, count: int) -> np.ndarray:
    identity = np.eye(operator.shape[0], dtype=complex)
    result = np.array([[1.0 + 0.0j]])
    for index in range(count):
        result = np.kron(result, operator if index == site else identity)
    return result


def kron_all(items: list[np.ndarray]) -> np.ndarray:
    result = np.array([[1.0 + 0.0j]])
    for item in items:
        result = np.kron(result, item)
    return result


def build_model(
    *, config: Config, mode_count: int, frequencies: tuple[float, ...], coupling: float
) -> dict[str, np.ndarray]:
    if len(frequencies) != mode_count:
        raise ValueError("frequency count mismatch")
    annihilation = np.array([[0.0, 1.0], [0.0, 0.0]], dtype=complex)
    number = annihilation.conj().T @ annihilation
    position = (annihilation + annihilation.conj().T) / np.sqrt(2.0)
    numbers = [local_operator(number, i, mode_count) for i in range(mode_count)]
    positions = [local_operator(position, i, mode_count) for i in range(mode_count)]
    h0 = sum(w * n for w, n in zip(frequencies, numbers, strict=True))
    local = config.local_perturbation_strength / np.sqrt(mode_count) * sum(
        w * x for w, x in zip(frequencies, positions, strict=True)
    )
    interaction = sum(
        coupling
        * np.sqrt(frequencies[i] * frequencies[i + 1])
        * (positions[i] @ positions[i + 1])
        for i in range(mode_count - 1)
    )
    h1 = hermitize(h0 + local + interaction)
    return {
        "H0": h0,
        "H1": h1,
        "rho0": thermal_state(h0, config.beta),
        "rho1": thermal_state(h1, config.beta),
        "Xsum": sum(positions) / np.sqrt(mode_count),
        "Ntotal": sum(numbers),
        "I": np.eye(2**mode_count, dtype=complex),
    }


def one_mode_states(*, omega: float, local_coefficient: float, beta: float) -> tuple[np.ndarray, np.ndarray]:
    annihilation = np.array([[0.0, 1.0], [0.0, 0.0]], dtype=complex)
    number = annihilation.conj().T @ annihilation
    position = (annihilation + annihilation.conj().T) / np.sqrt(2.0)
    h0 = omega * number
    h1 = hermitize(h0 + local_coefficient * omega * position)
    return thermal_state(h0, beta), thermal_state(h1, beta)


def algebra_metrics(*, config: Config, mode_count: int, frequencies: tuple[float, ...]) -> dict[str, float]:
    model = build_model(
        config=config,
        mode_count=mode_count,
        frequencies=frequencies,
        coupling=config.nearest_neighbor_coupling,
    )
    maximum_unitarity = 0.0
    maximum_chain = 0.0
    maximum_transport = 0.0
    maximum_group = 0.0
    observables = (model["Xsum"], model["Ntotal"])
    for s in S_VALUES:
        u_s = cocycle(model["rho1"], model["rho0"], s)
        maximum_unitarity = max(
            maximum_unitarity,
            relative_frobenius(u_s.conj().T @ u_s, model["I"]),
        )
        for observable in observables:
            target = modular_flow(model["rho1"], observable, s)
            transported = u_s @ modular_flow(model["rho0"], observable, s) @ u_s.conj().T
            maximum_transport = max(maximum_transport, relative_frobenius(transported, target))
        for t in S_VALUES:
            left = cocycle(model["rho1"], model["rho0"], s + t)
            right = u_s @ modular_flow(model["rho0"], cocycle(model["rho1"], model["rho0"], t), s)
            maximum_chain = max(maximum_chain, relative_frobenius(right, left))
            for observable in observables:
                composed = modular_flow(model["rho1"], modular_flow(model["rho1"], observable, t), s)
                direct = modular_flow(model["rho1"], observable, s + t)
                maximum_group = max(maximum_group, relative_frobenius(composed, direct))
    values = np.concatenate((np.linalg.eigvalsh(model["rho0"]), np.linalg.eigvalsh(model["rho1"])))
    trace_error = max(abs(np.trace(model["rho0"]).real - 1.0), abs(np.trace(model["rho1"]).real - 1.0))
    return {
        "minimum_density_eigenvalue": float(values.min()),
        "maximum_trace_error": float(trace_error),
        "maximum_unitarity_residual": maximum_unitarity,
        "maximum_chain_residual": maximum_chain,
        "maximum_transport_residual": maximum_transport,
        "maximum_modular_group_residual": maximum_group,
    }


def factorization_metrics(*, config: Config, mode_count: int, frequencies: tuple[float, ...], s: float = 0.25) -> dict[str, float]:
    uncoupled = build_model(config=config, mode_count=mode_count, frequencies=frequencies, coupling=0.0)
    coupled = build_model(
        config=config,
        mode_count=mode_count,
        frequencies=frequencies,
        coupling=config.nearest_neighbor_coupling,
    )
    local_coefficient = config.local_perturbation_strength / np.sqrt(mode_count)
    expected_terms: list[np.ndarray] = []
    for omega in frequencies:
        rho0, rho1 = one_mode_states(omega=omega, local_coefficient=local_coefficient, beta=config.beta)
        expected_terms.append(cocycle(rho1, rho0, s))
    expected = kron_all(expected_terms)
    return {
        "uncoupled_factorization_residual": relative_frobenius(cocycle(uncoupled["rho1"], uncoupled["rho0"], s), expected),
        "coupled_nonfactorization_residual": relative_frobenius(cocycle(coupled["rho1"], coupled["rho0"], s), expected),
    }


def transition_entries(observable: np.ndarray, hamiltonian: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    energies, basis = np.linalg.eigh(hermitize(hamiltonian))
    rotated = basis.conj().T @ observable @ basis
    rows, cols = np.nonzero(np.abs(rotated) > 1.0e-15)
    return (energies[rows] - energies[cols]).real, (np.abs(rotated[rows, cols]) ** 2).real


def clock_difference_classes(*, q_max: float, intervals: int) -> tuple[np.ndarray, np.ndarray, float]:
    delta_q = q_max / intervals
    indices = np.arange(-intervals, intervals + 1)
    return indices * delta_q, (intervals + 1 - np.abs(indices)).astype(float), delta_q


def select_intervals(*, q_max: float, averaging_width: float, eta_target: float, gaps: np.ndarray) -> int:
    intervals = max(1, math.ceil(q_max * averaging_width / eta_target))
    active = [abs(float(g)) for g in gaps if abs(float(g)) > 1.0e-10]
    while True:
        delta_q = q_max / intervals
        if all(abs(g / delta_q - round(g / delta_q)) > 1.0e-8 for g in active):
            return intervals
        intervals += 1


def filtered_norm_squared(
    *, observable: np.ndarray, hamiltonian: np.ndarray, config: Config, t_ratio: float, eta_target: float
) -> tuple[float, float, float, int]:
    gaps, matter_weights = transition_entries(observable, hamiltonian)
    averaging_width = t_ratio * config.beta
    intervals = select_intervals(q_max=config.q_max, averaging_width=averaging_width, eta_target=eta_target, gaps=gaps)
    differences, multiplicities, delta_q = clock_difference_classes(q_max=config.q_max, intervals=intervals)
    clock_weights = multiplicities * np.exp(-((config.sigma_ratio * config.beta) * differences) ** 2)
    filtered = 0.0
    unfiltered = 0.0
    for gap, weight in zip(gaps, matter_weights, strict=True):
        filter_squared = np.exp(-(averaging_width * (gap + differences)) ** 2)
        filtered += float(weight * np.sum(clock_weights * filter_squared))
        unfiltered += float(weight * np.sum(clock_weights))
    return filtered, unfiltered, delta_q, intervals


def readout_metrics(
    *, config: Config, mode_count: int, frequencies: tuple[float, ...], t_ratio: float, eta_target: float, s: float = 0.25
) -> dict[str, float | int]:
    model = build_model(
        config=config,
        mode_count=mode_count,
        frequencies=frequencies,
        coupling=config.nearest_neighbor_coupling,
    )
    reference = modular_flow(model["rho0"], model["Xsum"], s)
    perturbed = modular_flow(model["rho1"], model["Xsum"], s)
    transported = cocycle(model["rho1"], model["rho0"], s) @ reference @ cocycle(model["rho1"], model["rho0"], s).conj().T
    numerator, _, delta_q, intervals = filtered_norm_squared(
        observable=perturbed - reference,
        hamiltonian=model["H0"],
        config=config,
        t_ratio=t_ratio,
        eta_target=eta_target,
    )
    denominator, _, _, _ = filtered_norm_squared(
        observable=reference,
        hamiltonian=model["H0"],
        config=config,
        t_ratio=t_ratio,
        eta_target=eta_target,
    )
    perturbed_filtered, perturbed_unfiltered, _, _ = filtered_norm_squared(
        observable=perturbed,
        hamiltonian=model["H0"],
        config=config,
        t_ratio=t_ratio,
        eta_target=eta_target,
    )
    transport_filtered, _, _, _ = filtered_norm_squared(
        observable=transported - perturbed,
        hamiltonian=model["H0"],
        config=config,
        t_ratio=t_ratio,
        eta_target=eta_target,
    )
    if min(denominator, perturbed_filtered, perturbed_unfiltered) <= 0.0:
        raise FloatingPointError("regulated norm vanished")
    return {
        "physical_modular_mismatch": relative_frobenius(perturbed, reference),
        "readout_modular_mismatch": float(np.sqrt(max(0.0, numerator) / denominator)),
        "readout_cocycle_transport_residual": float(np.sqrt(max(0.0, transport_filtered) / perturbed_filtered)),
        "observable_retention": float(np.sqrt(perturbed_filtered / perturbed_unfiltered)),
        "delta_q": float(delta_q),
        "T_delta_q": float(t_ratio * config.beta * delta_q),
        "N_q": intervals + 1,
    }


def relative_change(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1.0e-300)


def build_payload() -> dict[str, Any]:
    config = Config()
    scans: dict[str, Any] = {}
    max_identity = 0.0
    max_trace = 0.0
    min_support = math.inf
    max_factorization = 0.0
    min_nonfactorization = math.inf
    min_physical = math.inf
    min_readout = math.inf
    min_retention = math.inf
    max_transport = 0.0
    max_refinement = 0.0

    for mode_count in MODE_COUNTS:
        frequencies = BASE_FREQUENCIES[:mode_count]
        algebra = algebra_metrics(config=config, mode_count=mode_count, frequencies=frequencies)
        factor = factorization_metrics(config=config, mode_count=mode_count, frequencies=frequencies)
        readout: dict[str, Any] = {}
        for t_ratio in T_RATIOS:
            coarse = readout_metrics(
                config=config,
                mode_count=mode_count,
                frequencies=frequencies,
                t_ratio=t_ratio,
                eta_target=max(ETA_TARGETS),
            )
            fine = readout_metrics(
                config=config,
                mode_count=mode_count,
                frequencies=frequencies,
                t_ratio=t_ratio,
                eta_target=min(ETA_TARGETS),
            )
            readout[f"T_over_beta_{t_ratio:g}"] = {"coarse": coarse, "fine": fine}
            max_refinement = max(
                max_refinement,
                relative_change(float(coarse["readout_modular_mismatch"]), float(fine["readout_modular_mismatch"])),
                relative_change(float(coarse["observable_retention"]), float(fine["observable_retention"])),
            )
            min_physical = min(min_physical, float(fine["physical_modular_mismatch"]))
            min_readout = min(min_readout, float(fine["readout_modular_mismatch"]))
            min_retention = min(min_retention, float(fine["observable_retention"]))
            max_transport = max(max_transport, float(fine["readout_cocycle_transport_residual"]))
        scans[f"modes_{mode_count}"] = {"frequencies": frequencies, "algebra": algebra, "factorization": factor, "readout": readout}
        max_identity = max(
            max_identity,
            algebra["maximum_unitarity_residual"],
            algebra["maximum_chain_residual"],
            algebra["maximum_transport_residual"],
            algebra["maximum_modular_group_residual"],
        )
        max_trace = max(max_trace, algebra["maximum_trace_error"])
        min_support = min(min_support, algebra["minimum_density_eigenvalue"])
        max_factorization = max(max_factorization, factor["uncoupled_factorization_residual"])
        min_nonfactorization = min(min_nonfactorization, factor["coupled_nonfactorization_residual"])

    thresholds = {
        "finite_matrix_identity_residual_max": 1.0e-10,
        "trace_error_max": 1.0e-12,
        "uncoupled_factorization_residual_max": 1.0e-8,
        "coupled_nonfactorization_residual_min": 1.0e-4,
        "readout_transport_residual_max": 1.0e-9,
        "nontrivial_physical_mismatch_min": 1.0e-4,
        "nontrivial_readout_mismatch_min": 1.0e-5,
        "eta_refinement_relative_change_max": 2.0e-2,
        "minimum_observable_retention": 1.0e-4,
    }
    gates = {
        "faithful_density_support_all_mode_counts": min_support > 0.0,
        "density_trace_preservation_all_mode_counts": max_trace <= thresholds["trace_error_max"],
        "finite_cocycle_identities_all_mode_counts": max_identity <= thresholds["finite_matrix_identity_residual_max"],
        "uncoupled_tensor_factorization_all_mode_counts": max_factorization <= thresholds["uncoupled_factorization_residual_max"],
        "interaction_breaks_factorization_all_mode_counts": min_nonfactorization >= thresholds["coupled_nonfactorization_residual_min"],
        "nontrivial_physical_mismatch_all_mode_counts": min_physical >= thresholds["nontrivial_physical_mismatch_min"],
        "nontrivial_readout_mismatch_all_mode_counts": min_readout >= thresholds["nontrivial_readout_mismatch_min"],
        "readout_cocycle_transport_all_mode_counts": max_transport <= thresholds["readout_transport_residual_max"],
        "resolved_eta_refinement_all_mode_counts": max_refinement <= thresholds["eta_refinement_relative_change_max"],
        "nontrivial_retention_all_mode_counts": min_retention >= thresholds["minimum_observable_retention"],
    }
    passed = all(gates.values())
    source_path = Path(__file__).resolve()
    config_json = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return {
        "metadata": {
            "schema_version": 1,
            "classification": "EXPERIMENTAL",
            "dependency": "PASS_TWO_MODE_FINITE_TYPE_I_STRESS",
            "mode_counts": MODE_COUNTS,
            "continuum_connes_cocycle_status": "BLOCKED_NOT_ESTABLISHED_BY_FINITE_MATRICES",
            "overall_status": "PASS_BOUNDED_MULTI_MODE_REGULATOR_STRESS" if passed else "FAIL_BOUNDED_MULTI_MODE_REGULATOR_STRESS",
            "generated_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "platform": platform.platform(),
            "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "configuration_sha256": hashlib.sha256(config_json.encode()).hexdigest(),
        },
        "fixed_parameters": asdict(config),
        "scans": scans,
        "validation_summary": {
            "maximum_finite_identity_residual": max_identity,
            "maximum_trace_error": max_trace,
            "minimum_density_eigenvalue": min_support,
            "maximum_uncoupled_factorization_residual": max_factorization,
            "minimum_coupled_nonfactorization_residual": min_nonfactorization,
            "minimum_physical_modular_mismatch": min_physical,
            "minimum_readout_modular_mismatch": min_readout,
            "maximum_readout_cocycle_transport_residual": max_transport,
            "maximum_eta_refinement_relative_change": max_refinement,
            "minimum_observable_retention": min_retention,
            "thresholds": thresholds,
            "gates": gates,
            "overall_status": "PASS_BOUNDED_MULTI_MODE_REGULATOR_STRESS" if passed else "FAIL_BOUNDED_MULTI_MODE_REGULATOR_STRESS",
        },
        "interpretation_limits": [
            "Two through four truncated modes remain finite Type-I matrix algebras.",
            "Nearest-neighbor X_i X_{i+1} coupling is a stress interaction, not a derived field-theory coupling.",
            "PASS would establish bounded numerical stability only over the frozen 2-4 mode family.",
            "No continuum factor type, field-mode limit, or continuum Connes cocycle follows from this gate.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.strict and payload["validation_summary"]["overall_status"] != "PASS_BOUNDED_MULTI_MODE_REGULATOR_STRESS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
