"""Two-mode finite Type-I cocycle and resolved-clock stress test.

This candidate is downstream of the single-mode regulator and finite matrix cocycle
gates.  It introduces a second oscillator and a weak non-factorizing interaction to
check that the validated machinery is not an artifact of a one-mode tensor factor.
It remains a finite-dimensional Type-I calculation.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import math
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

SINGLE_MODE_PATH = (
    Path(__file__).resolve().parents[1]
    / "finite-type-i-cocycle-harness"
    / "cocycle_scan.py"
)
SPEC = importlib.util.spec_from_file_location("finite_type_i_cocycle_dependency", SINGLE_MODE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load finite-Type-I cocycle dependency")
SINGLE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SINGLE
SPEC.loader.exec_module(SINGLE)

BETA = 2.0 * np.pi
FREQUENCY_PAIRS = ((1.00, 1.37), (1.01, 1.37), (1.03, 1.41))
S_VALUES = (-0.25, -0.125, 0.0, 0.125, 0.25)
T_RATIOS = (1.0, 2.0, 4.0)
ETA_TARGETS = (0.125, 0.0625)
COUPLINGS = (0.0, 0.01, 0.02)


@dataclass(frozen=True)
class TwoModeConfig:
    n_cut_per_mode: int = 3
    beta: float = BETA
    q_max: float = 8.0
    sigma_ratio: float = 1.0 / 16.0
    local_perturbation_strength: float = 0.04
    interaction_strength: float = 0.02


def two_mode_model(
    *,
    config: TwoModeConfig,
    omega_1: float,
    omega_2: float,
    interaction_strength: float | None = None,
) -> dict[str, np.ndarray | float]:
    """Construct two truncated oscillators with a weak X1 X2 interaction."""
    n_cut = config.n_cut_per_mode
    first = SINGLE.oscillator_operators(n_cut, omega_1)
    second = SINGLE.oscillator_operators(n_cut, omega_2)
    identity = np.eye(n_cut, dtype=complex)

    n_1 = np.kron(first["N"], identity)
    n_2 = np.kron(identity, second["N"])
    x_1 = np.kron(first["X"], identity)
    x_2 = np.kron(identity, second["X"])
    x_cross = x_1 @ x_2
    identity_two = np.eye(n_cut * n_cut, dtype=complex)
    h_0 = omega_1 * n_1 + omega_2 * n_2

    coupling = (
        config.interaction_strength
        if interaction_strength is None
        else interaction_strength
    )
    local = config.local_perturbation_strength * (
        omega_1 * x_1 + omega_2 * x_2
    ) / np.sqrt(2.0)
    interaction = coupling * np.sqrt(omega_1 * omega_2) * x_cross
    h_1 = SINGLE.hermitize(h_0 + local + interaction)

    rho_0 = SINGLE.thermal_state(h_0, config.beta)
    rho_1 = SINGLE.thermal_state(h_1, config.beta)
    x_sum = (x_1 + x_2) / np.sqrt(2.0)
    n_total = n_1 + n_2

    return {
        "I": identity_two,
        "N1": n_1,
        "N2": n_2,
        "N_total": n_total,
        "X1": x_1,
        "X2": x_2,
        "X_sum": x_sum,
        "X_cross": x_cross,
        "H0": h_0,
        "H1": h_1,
        "rho0": rho_0,
        "rho1": rho_1,
        "omega_1": omega_1,
        "omega_2": omega_2,
        "interaction_strength": coupling,
    }


def finite_two_mode_cocycle_metrics(
    *,
    config: TwoModeConfig,
    omega_1: float,
    omega_2: float,
    interaction_strength: float,
) -> dict[str, float]:
    model = two_mode_model(
        config=config,
        omega_1=omega_1,
        omega_2=omega_2,
        interaction_strength=interaction_strength,
    )
    rho_0 = model["rho0"]
    rho_1 = model["rho1"]
    identity = model["I"]
    observables = (model["X_sum"], model["N_total"], model["X_cross"])

    rho_0_values = np.linalg.eigvalsh(rho_0)
    rho_1_values = np.linalg.eigvalsh(rho_1)
    maximum_unitarity = 0.0
    maximum_chain = 0.0
    maximum_transport = 0.0
    maximum_group = 0.0

    for s in S_VALUES:
        u_s = SINGLE.connes_cocycle(rho_1, rho_0, s)
        maximum_unitarity = max(
            maximum_unitarity,
            SINGLE.relative_frobenius(u_s.conj().T @ u_s, identity),
        )
        for observable in observables:
            target = SINGLE.modular_flow(rho_1, observable, s)
            transported = (
                u_s
                @ SINGLE.modular_flow(rho_0, observable, s)
                @ u_s.conj().T
            )
            maximum_transport = max(
                maximum_transport,
                SINGLE.relative_frobenius(transported, target),
            )

        for t in S_VALUES:
            u_t = SINGLE.connes_cocycle(rho_1, rho_0, t)
            left = SINGLE.connes_cocycle(rho_1, rho_0, s + t)
            right = u_s @ SINGLE.modular_flow(rho_0, u_t, s)
            maximum_chain = max(
                maximum_chain,
                SINGLE.relative_frobenius(right, left),
            )
            for observable in observables:
                direct = SINGLE.modular_flow(rho_1, observable, s + t)
                composed = SINGLE.modular_flow(
                    rho_1,
                    SINGLE.modular_flow(rho_1, observable, t),
                    s,
                )
                maximum_group = max(
                    maximum_group,
                    SINGLE.relative_frobenius(composed, direct),
                )

    return {
        "omega_1": omega_1,
        "omega_2": omega_2,
        "interaction_strength": interaction_strength,
        "rho0_min_eigenvalue": float(rho_0_values[0]),
        "rho1_min_eigenvalue": float(rho_1_values[0]),
        "rho0_trace_error": float(abs(np.trace(rho_0).real - 1.0)),
        "rho1_trace_error": float(abs(np.trace(rho_1).real - 1.0)),
        "maximum_unitarity_residual": maximum_unitarity,
        "maximum_cocycle_chain_residual": maximum_chain,
        "maximum_state_transport_residual": maximum_transport,
        "maximum_modular_group_residual": maximum_group,
    }


def factorization_metrics(
    *, config: TwoModeConfig, omega_1: float, omega_2: float, s: float = 0.25
) -> dict[str, float]:
    """Compare the uncoupled two-mode cocycle with the tensor-product prediction."""
    uncoupled = two_mode_model(
        config=config,
        omega_1=omega_1,
        omega_2=omega_2,
        interaction_strength=0.0,
    )
    coupled = two_mode_model(
        config=config,
        omega_1=omega_1,
        omega_2=omega_2,
        interaction_strength=config.interaction_strength,
    )

    first = SINGLE.oscillator_operators(config.n_cut_per_mode, omega_1)
    second = SINGLE.oscillator_operators(config.n_cut_per_mode, omega_2)
    h_1_first = SINGLE.hermitize(
        first["H"]
        + config.local_perturbation_strength * omega_1 * first["X"] / np.sqrt(2.0)
    )
    h_1_second = SINGLE.hermitize(
        second["H"]
        + config.local_perturbation_strength * omega_2 * second["X"] / np.sqrt(2.0)
    )
    rho_0_first = SINGLE.thermal_state(first["H"], config.beta)
    rho_0_second = SINGLE.thermal_state(second["H"], config.beta)
    rho_1_first = SINGLE.thermal_state(h_1_first, config.beta)
    rho_1_second = SINGLE.thermal_state(h_1_second, config.beta)
    expected = np.kron(
        SINGLE.connes_cocycle(rho_1_first, rho_0_first, s),
        SINGLE.connes_cocycle(rho_1_second, rho_0_second, s),
    )
    actual_uncoupled = SINGLE.connes_cocycle(
        uncoupled["rho1"], uncoupled["rho0"], s
    )
    actual_coupled = SINGLE.connes_cocycle(coupled["rho1"], coupled["rho0"], s)
    return {
        "uncoupled_factorization_residual": SINGLE.relative_frobenius(
            actual_uncoupled, expected
        ),
        "coupled_nonfactorization_residual": SINGLE.relative_frobenius(
            actual_coupled, expected
        ),
    }


def transition_entries(
    observable: np.ndarray, hamiltonian: np.ndarray, threshold: float = 1.0e-15
) -> tuple[np.ndarray, np.ndarray]:
    energies, basis = np.linalg.eigh(SINGLE.hermitize(hamiltonian))
    rotated = basis.conj().T @ observable @ basis
    rows, cols = np.nonzero(np.abs(rotated) > threshold)
    gaps = energies[rows] - energies[cols]
    weights = np.abs(rotated[rows, cols]) ** 2
    return gaps.real, weights.real


def select_resolved_intervals(
    *, q_max: float, averaging_width: float, eta_target: float, avoid_gaps: tuple[float, ...]
) -> int:
    intervals = max(1, math.ceil(q_max * averaging_width / eta_target))
    while True:
        delta_q = q_max / intervals
        offsets = [abs(gap / delta_q - round(gap / delta_q)) for gap in avoid_gaps]
        if all(offset > 1.0e-10 for offset in offsets):
            return intervals
        intervals += 1


def filtered_norm_squared(
    *,
    observable: np.ndarray,
    hamiltonian: np.ndarray,
    config: TwoModeConfig,
    t_ratio: float,
    n_intervals: int,
) -> tuple[float, float, float]:
    gaps, matter_weights = transition_entries(observable, hamiltonian)
    differences, multiplicities, delta_q = SINGLE.clock_difference_classes(
        q_max=config.q_max,
        n_intervals=n_intervals,
    )
    sigma_tau = config.sigma_ratio * config.beta
    averaging_width = t_ratio * config.beta
    clock_weights = multiplicities * np.exp(-(sigma_tau * differences) ** 2)
    filtered_norm2 = 0.0
    input_norm2 = 0.0
    for gap, matter_weight in zip(gaps, matter_weights, strict=True):
        constraint_difference = gap + differences
        filter_squared = np.exp(-(averaging_width * constraint_difference) ** 2)
        filtered_norm2 += float(matter_weight * np.sum(clock_weights * filter_squared))
        input_norm2 += float(matter_weight * np.sum(clock_weights))
    return filtered_norm2, input_norm2, delta_q


def readout_relative_difference(
    *,
    actual: np.ndarray,
    expected: np.ndarray,
    hamiltonian: np.ndarray,
    config: TwoModeConfig,
    t_ratio: float,
    n_intervals: int,
) -> float:
    numerator, _, _ = filtered_norm_squared(
        observable=actual - expected,
        hamiltonian=hamiltonian,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    denominator, _, _ = filtered_norm_squared(
        observable=expected,
        hamiltonian=hamiltonian,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    if denominator <= 0.0:
        raise FloatingPointError("reference readout norm vanished")
    return float(np.sqrt(max(0.0, numerator) / denominator))


def readout_retention(
    *,
    observable: np.ndarray,
    hamiltonian: np.ndarray,
    config: TwoModeConfig,
    t_ratio: float,
    n_intervals: int,
) -> float:
    filtered, unfiltered, _ = filtered_norm_squared(
        observable=observable,
        hamiltonian=hamiltonian,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    if filtered <= 0.0 or unfiltered <= 0.0:
        raise FloatingPointError("readout norm vanished")
    return float(np.sqrt(filtered / unfiltered))


def two_mode_readout_metrics(
    *,
    config: TwoModeConfig,
    omega_1: float,
    omega_2: float,
    t_ratio: float,
    eta_target: float,
    s: float = 0.25,
) -> dict[str, float | int | bool]:
    model = two_mode_model(config=config, omega_1=omega_1, omega_2=omega_2)
    h_0 = model["H0"]
    rho_0 = model["rho0"]
    rho_1 = model["rho1"]
    observable = model["X_sum"]
    u_s = SINGLE.connes_cocycle(rho_1, rho_0, s)
    reference_flow = SINGLE.modular_flow(rho_0, observable, s)
    perturbed_flow = SINGLE.modular_flow(rho_1, observable, s)
    transported = u_s @ reference_flow @ u_s.conj().T

    averaging_width = t_ratio * config.beta
    avoid_gaps = (
        omega_1,
        omega_2,
        abs(omega_1 - omega_2),
        omega_1 + omega_2,
    )
    n_intervals = select_resolved_intervals(
        q_max=config.q_max,
        averaging_width=averaging_width,
        eta_target=eta_target,
        avoid_gaps=avoid_gaps,
    )
    _, _, delta_q = filtered_norm_squared(
        observable=reference_flow,
        hamiltonian=h_0,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    exact_resonance = any(
        abs(gap / delta_q - round(gap / delta_q)) < 1.0e-10
        for gap in avoid_gaps
    )
    physical_mismatch = SINGLE.relative_frobenius(perturbed_flow, reference_flow)
    readout_mismatch = readout_relative_difference(
        actual=perturbed_flow,
        expected=reference_flow,
        hamiltonian=h_0,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    transport_residual = readout_relative_difference(
        actual=transported,
        expected=perturbed_flow,
        hamiltonian=h_0,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    retention = readout_retention(
        observable=perturbed_flow,
        hamiltonian=h_0,
        config=config,
        t_ratio=t_ratio,
        n_intervals=n_intervals,
    )
    return {
        "omega_1": omega_1,
        "omega_2": omega_2,
        "T_over_beta": t_ratio,
        "eta_target": eta_target,
        "N_q": n_intervals + 1,
        "delta_q": float(delta_q),
        "T_delta_q": float(averaging_width * delta_q),
        "exact_lattice_resonance": bool(exact_resonance),
        "physical_modular_mismatch": physical_mismatch,
        "readout_modular_mismatch": readout_mismatch,
        "readout_cocycle_transport_residual": transport_residual,
        "observable_retention": retention,
        "sqrt_T_ratio_scaled_retention": float(np.sqrt(t_ratio) * retention),
    }


def relative_change(a: float, b: float) -> float:
    return float(abs(a - b) / max(abs(b), 1.0e-300))


def build_validation_payload() -> dict[str, Any]:
    config = TwoModeConfig()

    algebra_scan: dict[str, Any] = {}
    factorization_scan: dict[str, Any] = {}
    for omega_1, omega_2 in FREQUENCY_PAIRS:
        key = f"omega_{omega_1:.2f}_{omega_2:.2f}"
        algebra_scan[key] = {}
        for coupling in COUPLINGS:
            algebra_scan[key][f"g_{coupling:.2f}"] = finite_two_mode_cocycle_metrics(
                config=config,
                omega_1=omega_1,
                omega_2=omega_2,
                interaction_strength=coupling,
            )
        factorization_scan[key] = factorization_metrics(
            config=config,
            omega_1=omega_1,
            omega_2=omega_2,
        )

    readout_scan: dict[str, Any] = {}
    readout_index: dict[tuple[float, float, float, float], dict[str, Any]] = {}
    for omega_1, omega_2 in FREQUENCY_PAIRS:
        key = f"omega_{omega_1:.2f}_{omega_2:.2f}"
        readout_scan[key] = {}
        for t_ratio in T_RATIOS:
            readout_scan[key][f"T_over_beta_{t_ratio:g}"] = {}
            for eta_target in ETA_TARGETS:
                metric = two_mode_readout_metrics(
                    config=config,
                    omega_1=omega_1,
                    omega_2=omega_2,
                    t_ratio=t_ratio,
                    eta_target=eta_target,
                )
                readout_scan[key][f"T_over_beta_{t_ratio:g}"][
                    f"eta_target_{eta_target:g}"
                ] = metric
                readout_index[(omega_1, omega_2, t_ratio, eta_target)] = metric

    target_algebra = [
        algebra_scan[f"omega_{omega_1:.2f}_{omega_2:.2f}"][
            f"g_{config.interaction_strength:.2f}"
        ]
        for omega_1, omega_2 in FREQUENCY_PAIRS
    ]
    maximum_unitarity = max(float(item["maximum_unitarity_residual"]) for item in target_algebra)
    maximum_chain = max(float(item["maximum_cocycle_chain_residual"]) for item in target_algebra)
    maximum_transport = max(float(item["maximum_state_transport_residual"]) for item in target_algebra)
    maximum_group = max(float(item["maximum_modular_group_residual"]) for item in target_algebra)
    minimum_support = min(
        min(float(item["rho0_min_eigenvalue"]), float(item["rho1_min_eigenvalue"]))
        for item in target_algebra
    )
    maximum_trace_error = max(
        max(float(item["rho0_trace_error"]), float(item["rho1_trace_error"]))
        for item in target_algebra
    )

    maximum_factorization_residual = max(
        float(item["uncoupled_factorization_residual"])
        for item in factorization_scan.values()
    )
    minimum_nonfactorization = min(
        float(item["coupled_nonfactorization_residual"])
        for item in factorization_scan.values()
    )

    refinement_changes: list[float] = []
    maximum_readout_transport = 0.0
    minimum_physical_mismatch = math.inf
    minimum_readout_mismatch = math.inf
    minimum_retention = math.inf
    any_resonance = False
    for omega_1, omega_2 in FREQUENCY_PAIRS:
        for t_ratio in T_RATIOS:
            coarse = readout_index[(omega_1, omega_2, t_ratio, max(ETA_TARGETS))]
            fine = readout_index[(omega_1, omega_2, t_ratio, min(ETA_TARGETS))]
            for field in ("readout_modular_mismatch", "observable_retention"):
                refinement_changes.append(
                    relative_change(float(coarse[field]), float(fine[field]))
                )
            maximum_readout_transport = max(
                maximum_readout_transport,
                float(fine["readout_cocycle_transport_residual"]),
            )
            minimum_physical_mismatch = min(
                minimum_physical_mismatch,
                float(fine["physical_modular_mismatch"]),
            )
            minimum_readout_mismatch = min(
                minimum_readout_mismatch,
                float(fine["readout_modular_mismatch"]),
            )
            minimum_retention = min(minimum_retention, float(fine["observable_retention"]))
            any_resonance = any_resonance or bool(fine["exact_lattice_resonance"])

    maximum_refinement_change = max(refinement_changes)
    thresholds = {
        "finite_matrix_identity_residual_max": 1.0e-10,
        "trace_error_max": 1.0e-12,
        "uncoupled_factorization_residual_max": 1.0e-10,
        "coupled_nonfactorization_residual_min": 1.0e-4,
        "readout_transport_residual_max": 1.0e-9,
        "nontrivial_physical_mismatch_min": 1.0e-4,
        "nontrivial_readout_mismatch_min": 1.0e-5,
        "eta_refinement_relative_change_max": 2.0e-2,
        "minimum_observable_retention": 1.0e-4,
    }
    gates = {
        "faithful_density_support": minimum_support > 0.0,
        "density_trace_preservation": maximum_trace_error <= thresholds["trace_error_max"],
        "cocycle_unitarity": maximum_unitarity <= thresholds["finite_matrix_identity_residual_max"],
        "cocycle_chain_rule": maximum_chain <= thresholds["finite_matrix_identity_residual_max"],
        "state_transport_identity": maximum_transport <= thresholds["finite_matrix_identity_residual_max"],
        "modular_group_identity": maximum_group <= thresholds["finite_matrix_identity_residual_max"],
        "uncoupled_tensor_factorization": maximum_factorization_residual
        <= thresholds["uncoupled_factorization_residual_max"],
        "interaction_breaks_factorization": minimum_nonfactorization
        >= thresholds["coupled_nonfactorization_residual_min"],
        "nontrivial_state_mismatch": minimum_physical_mismatch
        >= thresholds["nontrivial_physical_mismatch_min"],
        "nontrivial_readout_mismatch": minimum_readout_mismatch
        >= thresholds["nontrivial_readout_mismatch_min"],
        "readout_cocycle_transport": maximum_readout_transport
        <= thresholds["readout_transport_residual_max"],
        "resolved_eta_refinement": maximum_refinement_change
        <= thresholds["eta_refinement_relative_change_max"],
        "nontrivial_retention": minimum_retention >= thresholds["minimum_observable_retention"],
        "detuned_nonresonant_regulator": not any_resonance,
    }
    overall_pass = all(gates.values())

    source_path = Path(__file__).resolve()
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    config_json = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return {
        "metadata": {
            "schema_version": 1,
            "numerical_algebra": "two-mode finite-dimensional Type I matrix algebra with GNS-clock regulator",
            "continuum_target": "Type III_1 -> Type II_infinity -> Type II_1",
            "classification": "EXPERIMENTAL",
            "dependency": "PASS_FINITE_TYPE_I_COCYCLE_CONSISTENCY",
            "support_aware_logarithm": True,
            "logarithm_eigenvalue_floor": None,
            "two_mode_status": (
                "PASS_TWO_MODE_FINITE_TYPE_I_STRESS"
                if overall_pass
                else "FAIL_TWO_MODE_FINITE_TYPE_I_STRESS"
            ),
            "field_mode_range_status": (
                "READY_FOR_BOUNDED_MULTI_MODE_REGULATOR_TEST"
                if overall_pass
                else "BLOCKED_PENDING_TWO_MODE_STRESS"
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
        "finite_matrix_algebra_scan": algebra_scan,
        "factorization_scan": factorization_scan,
        "resolved_clock_readout_scan": readout_scan,
        "validation_summary": {
            "minimum_density_eigenvalue": minimum_support,
            "maximum_density_trace_error": maximum_trace_error,
            "maximum_cocycle_unitarity_residual": maximum_unitarity,
            "maximum_cocycle_chain_residual": maximum_chain,
            "maximum_state_transport_residual": maximum_transport,
            "maximum_modular_group_residual": maximum_group,
            "maximum_uncoupled_factorization_residual": maximum_factorization_residual,
            "minimum_coupled_nonfactorization_residual": minimum_nonfactorization,
            "minimum_nontrivial_physical_modular_mismatch": minimum_physical_mismatch,
            "minimum_nontrivial_readout_modular_mismatch": minimum_readout_mismatch,
            "maximum_readout_cocycle_transport_residual": maximum_readout_transport,
            "maximum_eta_refinement_relative_change": maximum_refinement_change,
            "minimum_observable_retention": minimum_retention,
            "thresholds": thresholds,
            "gates": gates,
            "overall_status": (
                "PASS_TWO_MODE_FINITE_TYPE_I_STRESS"
                if overall_pass
                else "FAIL_TWO_MODE_FINITE_TYPE_I_STRESS"
            ),
        },
        "interpretation_limits": [
            "Two oscillator modes remain a finite Type-I regulator, not a field algebra.",
            "The weak X1 X2 term is a stress-test interaction, not a derived de Sitter coupling.",
            "Passing tensor factorization and interaction nonfactorization only validates implementation structure.",
            "A bounded multi-mode regulator test may follow, but an unrestricted field-mode scan remains prohibited.",
            "Continuum Connes-cocycle physics remains blocked regardless of this finite test result.",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
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
    if args.strict and payload["validation_summary"]["overall_status"] != "PASS_TWO_MODE_FINITE_TYPE_I_STRESS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
