from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

BETA = 2.0 * math.pi
LATTICE_SIZES = (16, 32, 64, 128, 256)
MODULAR_S = (-0.20, -0.10, 0.10, 0.20)
CONTINUUM_MODES = (512, 1024)
GRID_POINTS = 8193


def integrate(y: np.ndarray, x: np.ndarray) -> float:
    trapezoid = getattr(np, "trapezoid", None)
    if trapezoid is not None:
        return float(trapezoid(y, x))
    return float(np.trapz(y, x))


def compact_bump(x: np.ndarray, center: float, radius: float) -> np.ndarray:
    z = (x - center) / radius
    out = np.zeros_like(x, dtype=float)
    mask = np.abs(z) < 1.0
    out[mask] = np.exp(-1.0 / (1.0 - z[mask] ** 2))
    return out


def l2_normalize(values: np.ndarray, x: np.ndarray) -> np.ndarray:
    norm = math.sqrt(integrate(values * values, x))
    if norm <= 0.0:
        raise ValueError("zero smearing norm")
    return values / norm


def smearing_specs() -> tuple[dict[str, object], ...]:
    return (
        {
            "name": "A_left",
            "region": (0.18, 0.42),
            "q_center": 0.29,
            "q_radius": 0.075,
            "p_center": 0.33,
            "p_radius": 0.060,
            "p_scale": 0.18,
        },
        {
            "name": "A_right",
            "region": (0.18, 0.42),
            "q_center": 0.35,
            "q_radius": 0.050,
            "p_center": 0.27,
            "p_radius": 0.055,
            "p_scale": -0.13,
        },
        {
            "name": "B_middle",
            "region": (0.12, 0.62),
            "q_center": 0.48,
            "q_radius": 0.090,
            "p_center": 0.40,
            "p_radius": 0.075,
            "p_scale": 0.11,
        },
        {
            "name": "C_outer",
            "region": (0.05, 0.95),
            "q_center": 0.67,
            "q_radius": 0.100,
            "p_center": 0.58,
            "p_radius": 0.085,
            "p_scale": -0.09,
        },
    )


def continuum_smearings(x: np.ndarray) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for spec in smearing_specs():
        q_raw = compact_bump(x, float(spec["q_center"]), float(spec["q_radius"]))
        p_raw = compact_bump(x, float(spec["p_center"]), float(spec["p_radius"]))
        q = l2_normalize(q_raw, x)
        p = float(spec["p_scale"]) * l2_normalize(p_raw, x)
        out[str(spec["name"])] = {
            "region": tuple(spec["region"]),
            "q": q,
            "p": p,
        }
    return out


def sine_coefficients(
    x: np.ndarray, values: np.ndarray, max_mode: int
) -> np.ndarray:
    coeff = np.empty(max_mode, dtype=float)
    for mode_number in range(1, max_mode + 1):
        mode = math.sqrt(2.0) * np.sin(mode_number * math.pi * x)
        coeff[mode_number - 1] = integrate(values * mode, x)
    return coeff


def continuum_vectors(max_mode: int) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    x = np.linspace(0.0, 1.0, GRID_POINTS)
    smearings = continuum_smearings(x)
    vectors: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name, data in smearings.items():
        vectors[name] = (
            sine_coefficients(x, data["q"], max_mode),
            sine_coefficients(x, data["p"], max_mode),
        )
    return vectors


def lattice_vectors(size: int) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    dx = 1.0 / (size + 1)
    sites = np.arange(1, size + 1, dtype=float)
    x = sites * dx
    mode_numbers = np.arange(1, size + 1, dtype=float)
    modes = np.sqrt(2.0 / (size + 1)) * np.sin(
        math.pi * np.outer(sites, mode_numbers) / (size + 1)
    )
    vectors: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for spec in smearing_specs():
        q_raw = compact_bump(x, float(spec["q_center"]), float(spec["q_radius"]))
        p_raw = compact_bump(x, float(spec["p_center"]), float(spec["p_radius"]))
        q_norm = math.sqrt(dx * float(np.sum(q_raw * q_raw)))
        p_norm = math.sqrt(dx * float(np.sum(p_raw * p_raw)))
        if q_norm <= 0.0 or p_norm <= 0.0:
            raise ValueError("lattice failed to resolve compact smearing")
        q = q_raw / q_norm
        p = float(spec["p_scale"]) * p_raw / p_norm
        vectors[str(spec["name"])] = (
            math.sqrt(dx) * (modes.T @ q),
            math.sqrt(dx) * (modes.T @ p),
        )
    return vectors


def continuum_omegas(max_mode: int) -> np.ndarray:
    return math.pi * np.arange(1, max_mode + 1, dtype=float)


def lattice_omegas(size: int) -> np.ndarray:
    dx = 1.0 / (size + 1)
    mode_numbers = np.arange(1, size + 1, dtype=float)
    return (2.0 / dx) * np.sin(
        math.pi * mode_numbers / (2.0 * (size + 1))
    )


def evolve_for_time(
    vector: tuple[np.ndarray, np.ndarray], omegas: np.ndarray, t: float
) -> tuple[np.ndarray, np.ndarray]:
    f, g = vector
    cosine = np.cos(omegas * t)
    sine = np.sin(omegas * t)
    return (
        f * cosine - omegas * g * sine,
        f * sine / omegas + g * cosine,
    )


def modular_evolve(
    vector: tuple[np.ndarray, np.ndarray], omegas: np.ndarray, s: float
) -> tuple[np.ndarray, np.ndarray]:
    return evolve_for_time(vector, omegas, -BETA * s)


def covariance(
    left: tuple[np.ndarray, np.ndarray],
    right: tuple[np.ndarray, np.ndarray],
    omegas: np.ndarray,
) -> float:
    lf, lg = left
    rf, rg = right
    coth = 1.0 / np.tanh(BETA * omegas / 2.0)
    return float(
        np.sum(lf * rf * coth / (2.0 * omegas) + lg * rg * omegas * coth / 2.0)
    )


def symplectic(
    left: tuple[np.ndarray, np.ndarray], right: tuple[np.ndarray, np.ndarray]
) -> float:
    lf, lg = left
    rf, rg = right
    return float(np.sum(lf * rg - lg * rf))


def vector_add(
    left: tuple[np.ndarray, np.ndarray], right: tuple[np.ndarray, np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    return left[0] + right[0], left[1] + right[1]


def weyl_two_point(
    left: tuple[np.ndarray, np.ndarray],
    right: tuple[np.ndarray, np.ndarray],
    omegas: np.ndarray,
) -> complex:
    phase = np.exp(-0.5j * symplectic(left, right))
    total = vector_add(left, right)
    gaussian = math.exp(-0.5 * covariance(total, total, omegas))
    return complex(phase * gaussian)


def diagnostic_for(
    vectors: dict[str, tuple[np.ndarray, np.ndarray]], omegas: np.ndarray
) -> dict[str, object]:
    names = tuple(vectors)
    rows: list[dict[str, object]] = []
    max_invariance = 0.0
    for left_name in names:
        for right_name in names:
            left = vectors[left_name]
            right = vectors[right_name]
            for s in MODULAR_S:
                evolved = modular_evolve(right, omegas, s)
                value = weyl_two_point(left, evolved, omegas)
                var_before = covariance(right, right, omegas)
                var_after = covariance(evolved, evolved, omegas)
                invariance = abs(var_before - var_after) / max(1.0, abs(var_before))
                max_invariance = max(max_invariance, invariance)
                rows.append(
                    {
                        "left": left_name,
                        "right": right_name,
                        "s": s,
                        "real": float(value.real),
                        "imag": float(value.imag),
                        "modular_state_invariance_residual": float(invariance),
                    }
                )
    return {"rows": rows, "max_modular_state_invariance_residual": max_invariance}


def row_map(result: dict[str, object]) -> dict[tuple[str, str, float], complex]:
    out: dict[tuple[str, str, float], complex] = {}
    rows = result["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        key = (str(row["left"]), str(row["right"]), float(row["s"]))
        out[key] = complex(float(row["real"]), float(row["imag"]))
    return out


def max_complex_difference(
    left: dict[tuple[str, str, float], complex],
    right: dict[tuple[str, str, float], complex],
) -> float:
    if set(left) != set(right):
        raise ValueError("diagnostic grids differ")
    return max(abs(left[key] - right[key]) for key in left)


def locality_checks() -> dict[str, object]:
    x = np.linspace(0.0, 1.0, GRID_POINTS)
    smearings = continuum_smearings(x)
    support_residual = 0.0
    membership: dict[str, list[str]] = {}
    regions = {
        "A": (0.18, 0.42),
        "B": (0.12, 0.62),
        "C": (0.05, 0.95),
    }
    for name, data in smearings.items():
        region = tuple(data["region"])
        q = data["q"]
        p = data["p"]
        outside = (x <= region[0]) | (x >= region[1])
        support_residual = max(
            support_residual,
            float(np.max(np.abs(q[outside]))),
            float(np.max(np.abs(p[outside]))),
        )
        valid_regions = []
        for region_name, bounds in regions.items():
            if region[0] >= bounds[0] and region[1] <= bounds[1]:
                valid_regions.append(region_name)
        membership[name] = valid_regions
    isotony_ok = (
        membership["A_left"] == ["A", "B", "C"]
        and membership["A_right"] == ["A", "B", "C"]
        and membership["B_middle"] == ["B", "C"]
        and membership["C_outer"] == ["C"]
    )
    return {
        "support_residual": support_residual,
        "region_membership": membership,
        "nested_region_membership_consistent": isotony_ok,
    }


def wrong_modular_direction_gap() -> float:
    vectors = continuum_vectors(128)
    omegas = continuum_omegas(128)
    left = vectors["A_left"]
    right = vectors["B_middle"]
    s = 0.20
    correct = weyl_two_point(left, modular_evolve(right, omegas, s), omegas)
    wrong = weyl_two_point(
        left, evolve_for_time(right, omegas, +BETA * s), omegas
    )
    return float(abs(correct - wrong))


def evaluate() -> dict[str, object]:
    continuum_results: dict[int, dict[str, object]] = {}
    for max_mode in CONTINUUM_MODES:
        continuum_results[max_mode] = diagnostic_for(
            continuum_vectors(max_mode), continuum_omegas(max_mode)
        )
    reference = row_map(continuum_results[CONTINUUM_MODES[-1]])
    coarse_reference = row_map(continuum_results[CONTINUUM_MODES[0]])
    reference_refinement = max_complex_difference(reference, coarse_reference)

    lattice_rows: list[dict[str, object]] = []
    errors: list[float] = []
    invariance_residuals: list[float] = []
    for size in LATTICE_SIZES:
        result = diagnostic_for(lattice_vectors(size), lattice_omegas(size))
        error = max_complex_difference(row_map(result), reference)
        errors.append(error)
        invariance_residuals.append(float(result["max_modular_state_invariance_residual"]))
        lattice_rows.append(
            {
                "size": size,
                "max_modular_weyl_two_point_error": error,
                "max_modular_state_invariance_residual": result[
                    "max_modular_state_invariance_residual"
                ],
            }
        )

    fit_dx = np.array([1.0 / (size + 1) for size in LATTICE_SIZES[1:]])
    fit_errors = np.array(errors[1:])
    observed_order = float(np.polyfit(np.log(fit_dx), np.log(fit_errors), 1)[0])
    local = locality_checks()
    negative_gap = wrong_modular_direction_gap()

    checks = {
        "continuum_reference_refined": reference_refinement <= 1.0e-8,
        "final_modular_weyl_error": errors[-1] <= 2.0e-4,
        "refinement_improves_error": errors[-1] <= errors[0] / 20.0,
        "observed_convergence_order": observed_order >= 1.5,
        "finite_modular_state_invariance": max(invariance_residuals) <= 2.0e-12,
        "compact_support_respected": local["support_residual"] <= 1.0e-15,
        "nested_region_membership_consistent": local[
            "nested_region_membership_consistent"
        ]
        is True,
        "wrong_modular_direction_is_detected": negative_gap >= 1.0e-4,
    }
    passed = all(checks.values())
    return {
        "schema": "ds2.local-net-modular-diagnostic.v1",
        "execution_pass": passed,
        "scientific_pass": False,
        "status": "PASS_FROZEN_LOCAL_WEYL_MODULAR_CORRELATOR_SUBGATE"
        if passed
        else "FAIL_FROZEN_LOCAL_WEYL_MODULAR_CORRELATOR_SUBGATE",
        "checks": checks,
        "continuum_reference": {
            "mode_cutoffs": list(CONTINUUM_MODES),
            "max_512_to_1024_two_point_change": reference_refinement,
        },
        "lattice_refinement": {
            "sizes": list(LATTICE_SIZES),
            "rows": lattice_rows,
            "errors": errors,
            "observed_order": observed_order,
        },
        "negative_control": {
            "deliberate_error": "use alpha_{+beta*s} instead of alpha_{-beta*s}",
            "correct_vs_wrong_two_point_gap": negative_gap,
            "detected": negative_gap >= 1.0e-4,
        },
        "locality": local,
        "interpretation": {
            "established_if_pass": [
                "controlled finite-to-continuum convergence on one frozen finite family of compactly supported phase-space smearings",
                "convergence of thermal modular-flow Weyl two-point functions on the frozen modular-parameter grid",
                "consistent nested support bookkeeping for the frozen A subset B subset C interval family",
                "the declared negative control rejects reversal of the thermal modular-flow direction on the frozen probe",
            ],
            "not_established": [
                "density of the finite smearing family in the local one-particle or Weyl test space",
                "strong or weak operator convergence of the full local von Neumann net",
                "strong resolvent convergence of modular generators",
                "convergence of Tomita operators on a common core",
                "uniform modular-unitary convergence on all local observables",
                "Type-III1 classification from finite numerics",
                "interacting de Sitter convergence",
                "Type-II crossed-product gravity, Hollands-Wald energy, or Einstein dynamics",
            ],
            "promotion_ceiling": "FROZEN_FINITE_TEST_FAMILY_NECESSARY_SUBGATE_ONLY",
            "next_gate": "COMMON_GNS_OR_STANDARD_SUBSPACE_OPERATOR_TOPOLOGY_CONVERGENCE",
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
