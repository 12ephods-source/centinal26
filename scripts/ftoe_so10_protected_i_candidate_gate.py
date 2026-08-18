"""Fail-closed admission gate for explicit protected-I candidate files.

This gate evaluates a proposed lower-scale protected informational sector without
mutating the frozen SO(10) UV contract. A candidate may be explicit enough to
study while still failing admission. Scientific PASS requires all mechanism,
portal, radiative, spectrum, and running backreaction gates to be closed.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "physics" / "ftoe" / "protected_I_so5_so4_candidate.json"


def load_candidate(path: Path = DEFAULT_CANDIDATE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def break_even_scale(mu_i: float, alpha: float, coefficient: float) -> float:
    if min(mu_i, alpha, coefficient) <= 0.0:
        raise ValueError("mu_i, alpha, and coefficient must be positive")
    return mu_i / math.sqrt(coefficient * alpha / (4.0 * math.pi))


def closed(value: object) -> bool:
    return str(value).upper() in {"PASS", "DERIVED", "PROVED", "FROZEN", "VERIFIED"}


def evaluate(candidate: dict) -> dict:
    identification = candidate.get("candidate_identification", {})
    reference = candidate.get("reference_naturalness_bound", {})
    gates_in = candidate.get("mandatory_admission_gates", {})

    mu_i = float(reference["mu_I_GeV"])
    alpha = float(reference["alpha_reference"])
    coefficient = float(reference["coefficient_C_reference"])
    computed_bound = break_even_scale(mu_i, alpha, coefficient)
    recorded_bound = float(reference["break_even_f_GeV_reference"])
    bound_consistent = abs(computed_bound / recorded_bound - 1.0) < 5e-5

    f_scale = candidate.get("protection_scale_f_GeV")
    scale_frozen = isinstance(f_scale, (int, float)) and float(f_scale) > 0.0
    scale_below_reference_bound = bool(scale_frozen and float(f_scale) <= computed_bound)

    gates = {
        "explicit_nonlinear_coset": "PASS" if "SO5_OVER_SO4" in str(gates_in.get("explicit_nonlinear_coset", "")) else "FAIL",
        "I_doublet_identification": "PASS" if identification.get("sm_quantum_numbers") == "(1,2,+1/2)" else "FAIL",
        "reference_bound_reproduced": "PASS" if bound_consistent else "FAIL",
        "protection_scale_frozen": "PASS" if scale_frozen else "FAIL",
        "protection_scale_within_reference_bound": "PASS" if scale_below_reference_bound else "FAIL",
        "gauge_embedding_and_hypercharge": "PASS" if closed(gates_in.get("gauge_embedding_and_hypercharge")) else "FAIL",
        "collective_or_other_radiative_protection": "PASS" if closed(gates_in.get("collective_or_other_radiative_protection")) else "FAIL",
        "representation_specific_C": "PASS" if closed(gates_in.get("representation_specific_C")) else "FAIL",
        "renormalizable_SO10_portal_suppression": "PASS" if closed(gates_in.get("renormalizable_SO10_portal_suppression")) else "FAIL",
        "strong_sector_resonance_spectrum": "PASS" if closed(gates_in.get("strong_sector_resonance_spectrum")) else "FAIL",
        "beta_function_backreaction": "PASS" if closed(gates_in.get("beta_function_backreaction")) else "FAIL",
        "matching_to_existing_mu_I_and_G422_branch": "PASS" if closed(gates_in.get("matching_to_existing_mu_I_and_G422_branch")) else "FAIL",
    }
    admitted = all(value == "PASS" for value in gates.values())
    return {
        "schema": "FTOE-PROTECTED-I-CANDIDATE-GATE-v0.1",
        "candidate_status": candidate.get("status", "UNKNOWN"),
        "mechanism_class": candidate.get("mechanism_class", "UNKNOWN"),
        "global_symmetry_breaking": candidate.get("global_symmetry_breaking", "UNKNOWN"),
        "computed_reference_break_even_f_GeV": computed_bound,
        "candidate_protection_scale_f_GeV": f_scale,
        "gates": gates,
        "candidate_admission": "PASS" if admitted else "FAIL_CURRENT_CANDIDATE",
        "scientific_status": "REVIEW_PENDING_INDEPENDENT_REPRODUCTION" if admitted else "REVIEW",
        "derived_statement": (
            "The candidate is explicit enough to falsify, but it is not scientifically admitted until its gauge embedding, radiative protection, portal suppression, resonance spectrum, and beta-function backreaction are derived from one frozen mechanism."
            if not admitted
            else "The candidate satisfies the structural admission contract but still requires independent scientific reproduction."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = evaluate(load_candidate(args.candidate))
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
