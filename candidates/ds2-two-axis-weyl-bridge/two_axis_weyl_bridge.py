from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

BETA = 2.0 * math.pi
DIMENSIONS = (2, 4, 8, 12, 16, 24, 32)
BETA_OMEGA_GRID = (0.7, 1.5, 3.0)
ALPHA_GRID = (0.2, 0.5, 0.8)
LATTICE_SIZES = (16, 32, 64, 128, 256)
WEYL_AMPLITUDES = (0.5, 1.0, 1.5)


def annihilation(dimension: int) -> np.ndarray:
    matrix = np.zeros((dimension, dimension), dtype=np.complex128)
    for level in range(1, dimension):
        matrix[level - 1, level] = math.sqrt(level)
    return matrix


def antihermitian_exponential(generator: np.ndarray) -> np.ndarray:
    hermitian = -1j * generator
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    return (eigenvectors * np.exp(1j * eigenvalues)) @ eigenvectors.conj().T


def truncated_displacement_expectation(
    dimension: int, beta_omega: float, alpha: float
) -> complex:
    a = annihilation(dimension)
    generator = alpha * a.conj().T - alpha * a
    displacement = antihermitian_exponential(generator)
    levels = np.arange(dimension, dtype=float)
    weights = np.exp(-beta_omega * levels)
    weights /= np.sum(weights)
    return complex(np.sum(weights * np.diag(displacement)))


def exact_displacement_expectation(beta_omega: float, alpha: float) -> float:
    return float(np.exp(-0.5 * alpha**2 / np.tanh(beta_omega / 2.0)))


def local_dimension_scan() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    worst_errors: list[float] = []
    for dimension in DIMENSIONS:
        cases: list[dict[str, float]] = []
        errors: list[float] = []
        for beta_omega in BETA_OMEGA_GRID:
            for alpha in ALPHA_GRID:
                approximate = truncated_displacement_expectation(
                    dimension, beta_omega, alpha
                )
                exact = exact_displacement_expectation(beta_omega, alpha)
                error = float(abs(approximate - exact))
                errors.append(error)
                cases.append(
                    {
                        "beta_omega": beta_omega,
                        "alpha": alpha,
                        "absolute_error": error,
                    }
                )
        worst = max(errors)
        worst_errors.append(worst)
        rows.append(
            {
                "dimension": dimension,
                "worst_absolute_error": worst,
                "cases": cases,
            }
        )

    return {
        "dimensions": list(DIMENSIONS),
        "rows": rows,
        "worst_errors": worst_errors,
        "d2_worst_error": worst_errors[0],
        "d32_worst_error": worst_errors[-1],
        "improvement_ratio_d2_to_d32": worst_errors[0] / worst_errors[-1],
        "strictly_decreasing_worst_error": all(
            later < earlier for earlier, later in zip(worst_errors, worst_errors[1:])
        ),
    }


def integrate(y: np.ndarray, x: np.ndarray) -> float:
    trapezoid = getattr(np, "trapezoid", None)
    if trapezoid is not None:
        return float(trapezoid(y, x))
    return float(np.trapz(y, x))


def raw_smearing(x: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * ((x - 0.5) / 0.12) ** 2)


def continuum_covariance(
    max_mode: int, grid_points: int = 8193
) -> tuple[float, float]:
    x = np.linspace(0.0, 1.0, grid_points)
    smearing = raw_smearing(x)
    norm = math.sqrt(integrate(smearing * smearing, x))
    smearing /= norm

    total = 0.0
    for mode_number in range(1, max_mode + 1):
        mode = math.sqrt(2.0) * np.sin(mode_number * math.pi * x)
        coefficient = integrate(smearing * mode, x)
        omega = mode_number * math.pi
        coth = 1.0 / math.tanh(BETA * omega / 2.0)
        total += coefficient**2 / (2.0 * omega) * coth
    return total, norm


def lattice_covariance(size: int, smearing_norm: float) -> float:
    dx = 1.0 / (size + 1)
    sites = np.arange(1, size + 1, dtype=float)
    x = sites * dx
    smearing = raw_smearing(x) / smearing_norm
    mode_numbers = np.arange(1, size + 1, dtype=float)
    modes = np.sqrt(2.0 / (size + 1)) * np.sin(
        math.pi * np.outer(sites, mode_numbers) / (size + 1)
    )
    omega = (2.0 / dx) * np.sin(
        math.pi * mode_numbers / (2.0 * (size + 1))
    )
    coefficients = modes.T @ smearing
    coth = 1.0 / np.tanh(BETA * omega / 2.0)
    return float(
        dx * np.sum(np.abs(coefficients) ** 2 / (2.0 * omega) * coth)
    )


def spatial_mode_scan() -> dict[str, object]:
    continuum_256, smearing_norm = continuum_covariance(256)
    continuum_512, _ = continuum_covariance(512)
    reference_refinement = abs(continuum_512 - continuum_256)

    rows: list[dict[str, float | int]] = []
    errors: list[float] = []
    relative_errors: list[float] = []
    for size in LATTICE_SIZES:
        covariance = lattice_covariance(size, smearing_norm)
        error = abs(covariance - continuum_512)
        relative_error = error / abs(continuum_512)
        errors.append(error)
        relative_errors.append(relative_error)
        rows.append(
            {
                "lattice_size": size,
                "covariance": covariance,
                "absolute_error": error,
                "relative_error": relative_error,
            }
        )

    fit_dx = np.array([1.0 / (size + 1) for size in LATTICE_SIZES[1:]])
    observed_order = float(
        np.polyfit(np.log(fit_dx), np.log(np.array(errors[1:])), 1)[0]
    )

    final_covariance = rows[-1]["covariance"]
    assert isinstance(final_covariance, float)
    weyl_rows: list[dict[str, float]] = []
    weyl_errors: list[float] = []
    for amplitude in WEYL_AMPLITUDES:
        exact = math.exp(-0.5 * amplitude**2 * continuum_512)
        approximate = math.exp(-0.5 * amplitude**2 * final_covariance)
        error = abs(approximate - exact)
        weyl_errors.append(error)
        weyl_rows.append(
            {
                "amplitude": amplitude,
                "continuum_expectation": exact,
                "lattice_expectation": approximate,
                "absolute_error": error,
            }
        )

    return {
        "beta": BETA,
        "smearing": "L2-normalized Gaussian center=0.5 sigma=0.12 on unit Dirichlet interval",
        "continuum_covariance_m256": continuum_256,
        "continuum_covariance_m512": continuum_512,
        "continuum_reference_refinement": reference_refinement,
        "lattice_sizes": list(LATTICE_SIZES),
        "rows": rows,
        "errors": errors,
        "relative_errors": relative_errors,
        "strictly_decreasing_error": all(
            later < earlier for earlier, later in zip(errors, errors[1:])
        ),
        "observed_convergence_order": observed_order,
        "weyl_rows": weyl_rows,
        "max_final_weyl_error": max(weyl_errors),
    }


def evaluate() -> dict[str, object]:
    local = local_dimension_scan()
    spatial = spatial_mode_scan()

    checks = {
        "d2_is_not_continuum_accurate": local["d2_worst_error"] >= 5.0e-2,
        "local_dimension_error_decreases": local[
            "strictly_decreasing_worst_error"
        ]
        is True,
        "d32_bounded_displacement_error": local["d32_worst_error"] <= 1.0e-8,
        "local_dimension_improvement": local[
            "improvement_ratio_d2_to_d32"
        ]
        >= 1.0e6,
        "continuum_reference_refined": spatial[
            "continuum_reference_refinement"
        ]
        <= 1.0e-10,
        "spatial_error_decreases": spatial["strictly_decreasing_error"] is True,
        "spatial_second_order": spatial["observed_convergence_order"] >= 1.8,
        "final_spatial_relative_error": spatial["relative_errors"][-1] <= 2.0e-5,
        "final_bounded_weyl_error": spatial["max_final_weyl_error"] <= 5.0e-6,
    }

    return {
        "schema": "ds2.two-axis-weyl-bridge.v1",
        "execution_pass": all(checks.values()),
        "scientific_pass": False,
        "status": "PASS_TWO_AXIS_BOUNDED_WEYL_CORRELATOR_BRIDGE"
        if all(checks.values())
        else "FAIL_TWO_AXIS_BOUNDED_WEYL_CORRELATOR_BRIDGE",
        "checks": checks,
        "local_dimension_axis": local,
        "spatial_mode_axis": spatial,
        "interpretation": {
            "established": [
                "finite oscillator occupation cutoffs converge on the frozen bounded displacement-observable stress grid to the untruncated thermal oscillator result",
                "the d=2 local cutoff is quantitatively inadequate for this continuum bridge even though it remains valid for earlier bounded finite-Type-I stress tests",
                "the finite-difference free-field covariance for one smooth interior smearing converges approximately second order to the continuum Dirichlet mode result",
                "the associated bounded Weyl characteristic converges on the frozen amplitude grid",
            ],
            "not_established": [
                "convergence of the entire local Weyl net",
                "strong, weak, or modular convergence of local von Neumann algebras",
                "derivation of the Type-III1 factor classification from the finite regulator",
                "interacting de Sitter continuum convergence",
                "Type-II crossed-product gravity or Einstein dynamics",
            ],
            "next_gate": "LOCAL_NET_TOPOLOGY_AND_MODULAR_CONVERGENCE_CONTRACT",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()

    result = evaluate()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["execution_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
