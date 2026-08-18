"""Deterministic closure checks for FToE limitation L1.

This module deliberately separates numerical compatibility from UV derivation.
It does not claim that an SO(10) protecting symmetry or operator contraction has
been established.  Those remain explicit gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import log10, sqrt


@dataclass(frozen=True)
class L1Inputs:
    gut_scale_gev: float = 2.43e16
    planck_scale_gev: float = 1.22089e19
    mu_i_gev: float = 9.53e3
    xi_i: float = 1.0 / 6.0
    curvature_coefficient: float = 7.31


@dataclass(frozen=True)
class OperatorCandidate:
    suppression_power: int
    wilson_coefficient: float


@dataclass(frozen=True)
class L1Result:
    inputs: dict[str, float]
    hierarchy_mass_squared: float
    gut_to_planck: float
    preferred_operator: dict[str, float | int]
    lambda_x_gev: float
    beta: float
    physical_scalar_mass_gev: float
    seesaw_mix_scale_gev: float
    gates: dict[str, str]
    overall: str


def operator_scan(inputs: L1Inputs, n_min: int = 1, n_max: int = 12) -> list[OperatorCandidate]:
    hierarchy = (inputs.mu_i_gev / inputs.gut_scale_gev) ** 2
    ratio = inputs.gut_scale_gev / inputs.planck_scale_gev
    return [
        OperatorCandidate(n, hierarchy / ratio**n)
        for n in range(n_min, n_max + 1)
    ]


def preferred_operator(inputs: L1Inputs) -> OperatorCandidate:
    """Return the suppression power whose Wilson coefficient is closest to O(1)."""
    return min(operator_scan(inputs), key=lambda x: abs(log10(x.wilson_coefficient)))


def lambda_x_from_mu(inputs: L1Inputs) -> float:
    prefactor = inputs.curvature_coefficient * inputs.xi_i / 2.0
    return (inputs.mu_i_gev**2 * inputs.planck_scale_gev**2 / prefactor) ** 0.25


def beta_from_lambda_x(inputs: L1Inputs, lambda_x_gev: float) -> float:
    return (lambda_x_gev / inputs.planck_scale_gev) ** 2


def evaluate_l1(
    inputs: L1Inputs = L1Inputs(),
    *,
    representation_gate: str = "EXTERNAL_SOURCE_PASS",
    invariant_gate: str = "EXTERNAL_SOURCE_PASS",
    protecting_symmetry_gate: str = "NOT_TESTED",
    lower_operator_exclusion_gate: str = "NOT_TESTED",
    vacuum_solution_gate: str = "NOT_TESTED",
    threshold_backreaction_gate: str = "NOT_TESTED",
) -> L1Result:
    hierarchy = (inputs.mu_i_gev / inputs.gut_scale_gev) ** 2
    ratio = inputs.gut_scale_gev / inputs.planck_scale_gev
    op = preferred_operator(inputs)
    lambda_x = lambda_x_from_mu(inputs)
    beta = beta_from_lambda_x(inputs, lambda_x)

    operator_gate = (
        "PASS"
        if op.suppression_power == 9 and 0.1 <= op.wilson_coefficient <= 10.0
        else "REVIEW"
    )
    beta_gate = "PASS" if abs(log10(beta / 1.0e-15)) < 0.01 else "FAIL"

    gates = {
        "doublet_representation_exists": representation_gate,
        "10x126x210_invariant_exists": invariant_gate,
        "minimal_45_126_10_naturalness": "FAIL",
        "dimension_13_hierarchy_numerics": operator_gate,
        "noncircular_beta_chain_numerics": beta_gate,
        "explicit_protecting_symmetry": protecting_symmetry_gate,
        "lower_dimension_operator_exclusion": lower_operator_exclusion_gate,
        "full_so10_vacuum_solution": vacuum_solution_gate,
        "threshold_and_proton_decay_backreaction": threshold_backreaction_gate,
    }

    mandatory = (
        "doublet_representation_exists",
        "10x126x210_invariant_exists",
        "dimension_13_hierarchy_numerics",
        "noncircular_beta_chain_numerics",
        "explicit_protecting_symmetry",
        "lower_dimension_operator_exclusion",
        "full_so10_vacuum_solution",
        "threshold_and_proton_decay_backreaction",
    )
    if any(gates[name] == "FAIL" for name in mandatory):
        overall = "FAIL"
    elif any(gates[name] in {"NOT_TESTED", "REVIEW"} for name in mandatory):
        overall = "REVIEW"
    else:
        overall = "PASS"

    return L1Result(
        inputs=asdict(inputs),
        hierarchy_mass_squared=hierarchy,
        gut_to_planck=ratio,
        preferred_operator=asdict(op),
        lambda_x_gev=lambda_x,
        beta=beta,
        physical_scalar_mass_gev=sqrt(2.0) * inputs.mu_i_gev,
        seesaw_mix_scale_gev=sqrt(inputs.mu_i_gev * inputs.gut_scale_gev),
        gates=gates,
        overall=overall,
    )
