"""Finite dS2 regional quantum-Markov network-invariant candidate.

The invariant is state-only:

    I_net = sum_i I(site_i : site_i+2 | site_i+1)

on a four-site chain. Conditional mutual information is used because it quantifies
failure of the local quantum-Markov/recovery property without choosing an unbounded
quadrature as the invariant itself. The already-qualified modular-leakage result
remains parent evidence; this module tests a regulator trend for a complementary
state-only obstruction.

This is not a spacetime invariant, a gluing theorem, or a continuum factor result.
Thresholds were frozen after an exploratory cutoff study and before GitHub CI; this
is therefore a confirmatory engineering qualification of a candidate, not a blinded
scientific preregistration.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
CANDIDATES = HERE.parent
BETA = 2.0 * np.pi
X_MAX = 4.0
N_SITE = 4
N_CUT_SCAN = (3, 4, 5, 6)
COUPLING_SCAN = (0.0, 0.25, 0.5, 0.75, 1.0)
COUPLING_SHAPE_REFERENCE_N_CUT = 5

THRESHOLDS = {
    "split_network_invariant_abs_max": 1.0e-10,
    "full_network_invariant_min": 1.0e-3,
    "reflection_relative_max": 1.0e-10,
    "ncut_5_to_6_relative_change_max": 0.10,
    "successive_difference_contraction_max": 0.75,
    "local_unitary_invariance_abs_max": 1.0e-10,
}


def load_parent_module(name: str, relative_path: str):
    path = CANDIDATES / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REGIONAL = load_parent_module(
    "ds_regional_modular_overlap_parent",
    "ds-regional-modular-overlap/regional_modular_overlap_scan.py",
)
DS = REGIONAL.DS


def embed_local(op: np.ndarray, site: int, n_cut: int) -> np.ndarray:
    if not 0 <= site < N_SITE:
        raise ValueError("site index out of range")
    identity = np.eye(n_cut, dtype=complex)
    return REGIONAL.kron_all(
        [op if i == site else identity for i in range(N_SITE)]
    )


def chain_hamiltonian(n_cut: int, coupling_fraction: float) -> np.ndarray:
    if n_cut < 2:
        raise ValueError("n_cut must be >= 2")
    if not 0.0 <= coupling_fraction <= 1.0:
        raise ValueError("coupling_fraction must be in [0,1]")

    a = REGIONAL.annihilation(n_cut)
    q_local = (a + a.conj().T) / np.sqrt(2.0)
    p_local = 1j * (a.conj().T - a) / np.sqrt(2.0)
    q_ops = [embed_local(q_local, i, n_cut) for i in range(N_SITE)]
    p_ops = [embed_local(p_local, i, n_cut) for i in range(N_SITE)]

    kernel = DS.laplacian_matrix(N_SITE, x_max=X_MAX)
    diagonal = np.diag(np.diag(kernel))
    kernel = diagonal + coupling_fraction * (kernel - diagonal)

    dim = n_cut**N_SITE
    h = np.zeros((dim, dim), dtype=complex)
    for p_op in p_ops:
        h += 0.5 * (p_op @ p_op)
    for i in range(N_SITE):
        for j in range(N_SITE):
            h += 0.5 * kernel[i, j] * (q_ops[i] @ q_ops[j])
    return 0.5 * (h + h.conj().T)


def partial_trace(
    rho: np.ndarray, keep: tuple[int, ...], n_cut: int
) -> np.ndarray:
    if not keep or any(i < 0 or i >= N_SITE for i in keep):
        raise ValueError("invalid subsystem selection")
    if tuple(sorted(set(keep))) != keep:
        raise ValueError("keep must be sorted and unique")

    dims = [n_cut] * N_SITE
    trace = tuple(i for i in range(N_SITE) if i not in keep)
    n = N_SITE
    permutation = (
        list(keep)
        + list(trace)
        + [i + n for i in keep]
        + [i + n for i in trace]
    )
    tensor = rho.reshape(dims + dims).transpose(permutation)
    d_keep = n_cut ** len(keep)
    d_trace = n_cut ** len(trace)
    tensor = tensor.reshape(d_keep, d_trace, d_keep, d_trace)
    return np.einsum("atbt->ab", tensor)


def entropy(rho: np.ndarray) -> float:
    vals = np.linalg.eigvalsh(0.5 * (rho + rho.conj().T))
    vals = vals[vals > 1.0e-15]
    return float(-np.sum(vals * np.log(vals)))


def conditional_mutual_information(
    rho: np.ndarray, a: int, b: int, c: int, n_cut: int
) -> float:
    if not (0 <= a < b < c < N_SITE) or not (b == a + 1 and c == b + 1):
        raise ValueError("CMI triplet must be three adjacent ordered sites")
    s_ab = entropy(partial_trace(rho, (a, b), n_cut))
    s_bc = entropy(partial_trace(rho, (b, c), n_cut))
    s_b = entropy(partial_trace(rho, (b,), n_cut))
    s_abc = entropy(partial_trace(rho, (a, b, c), n_cut))
    value = s_ab + s_bc - s_b - s_abc
    if value < -1.0e-10:
        raise FloatingPointError("strong subadditivity violated beyond tolerance")
    return float(max(value, 0.0))


def network_profile(rho: np.ndarray, n_cut: int) -> np.ndarray:
    return np.array(
        [
            conditional_mutual_information(rho, 0, 1, 2, n_cut),
            conditional_mutual_information(rho, 1, 2, 3, n_cut),
        ],
        dtype=float,
    )


def network_invariant(rho: np.ndarray, n_cut: int) -> float:
    return float(np.sum(network_profile(rho, n_cut)))


def deterministic_local_unitary(n_cut: int) -> np.ndarray:
    phases = np.exp(1j * np.linspace(0.0, 0.71, n_cut))
    factors = [
        np.diag(phases),
        np.diag(np.conj(phases[::-1])),
        np.diag(np.exp(1j * np.linspace(0.0, 0.37, n_cut))),
        np.diag(np.exp(-1j * np.linspace(0.0, 0.29, n_cut))),
    ]
    return REGIONAL.kron_all(factors)


def source_hashes() -> dict[str, str]:
    paths = {
        "this_source": Path(__file__).resolve(),
        "regional_parent": CANDIDATES
        / "ds-regional-modular-overlap/regional_modular_overlap_scan.py",
        "geometry_parent": CANDIDATES
        / "ds-diamond-relational-harness/ds_diamond_relational_scan.py",
    }
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths.items()
    }


def scan() -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    full_by_cut: dict[int, float] = {}
    split_abs_max = 0.0
    reflection_max = 0.0
    monotonic_reference_cut = True
    rho6_full: np.ndarray | None = None

    for n_cut in N_CUT_SCAN:
        couplings = (
            COUPLING_SCAN
            if n_cut == COUPLING_SHAPE_REFERENCE_N_CUT
            else (0.0, 1.0)
        )
        coupling_rows: list[dict[str, Any]] = []
        prior: float | None = None

        for coupling in couplings:
            rho = REGIONAL.thermal(chain_hamiltonian(n_cut, coupling))
            if n_cut == 6 and coupling == 1.0:
                rho6_full = rho
            profile = network_profile(rho, n_cut)
            invariant = float(np.sum(profile))
            reflection_rel = float(
                abs(profile[0] - profile[1])
                / max(abs(profile[0]), abs(profile[1]), 1.0e-30)
            )
            if coupling == 0.0:
                split_abs_max = max(split_abs_max, abs(invariant))
            else:
                reflection_max = max(reflection_max, reflection_rel)
            if (
                n_cut == COUPLING_SHAPE_REFERENCE_N_CUT
                and prior is not None
                and invariant <= prior
            ):
                monotonic_reference_cut = False
            prior = invariant
            coupling_rows.append(
                {
                    "coupling_fraction": coupling,
                    "cmi_profile": profile.tolist(),
                    "network_invariant": invariant,
                    "reflection_relative_difference": reflection_rel,
                }
            )

        full_by_cut[n_cut] = coupling_rows[-1]["network_invariant"]
        rows[str(n_cut)] = {"coupling_scan": coupling_rows}

    diff_45 = abs(full_by_cut[5] - full_by_cut[4])
    diff_56 = abs(full_by_cut[6] - full_by_cut[5])
    rel_56 = diff_56 / max(abs(full_by_cut[6]), 1.0e-30)
    contraction = diff_56 / max(diff_45, 1.0e-30)

    if rho6_full is None:
        raise RuntimeError("n_cut=6 physical state was not evaluated")
    base = network_invariant(rho6_full, 6)
    u = deterministic_local_unitary(6)
    transformed = u @ rho6_full @ u.conj().T
    local_unitary_defect = abs(network_invariant(transformed, 6) - base)

    gates = {
        "NET1_split_markov_control": split_abs_max
        <= THRESHOLDS["split_network_invariant_abs_max"],
        "NET2_geometry_network_nontrivial": full_by_cut[6]
        >= THRESHOLDS["full_network_invariant_min"],
        "NET3_coupling_monotonicity": monotonic_reference_cut,
        "NET4_reflection_symmetry": reflection_max
        <= THRESHOLDS["reflection_relative_max"],
        "NET5_cutoff_refinement": rel_56
        <= THRESHOLDS["ncut_5_to_6_relative_change_max"]
        and contraction <= THRESHOLDS["successive_difference_contraction_max"],
        "NET6_local_unitary_invariance": local_unitary_defect
        <= THRESHOLDS["local_unitary_invariance_abs_max"],
    }
    passed = all(gates.values())

    config = {
        "beta_dS": float(BETA),
        "x_max": X_MAX,
        "n_site": N_SITE,
        "n_cut_scan": list(N_CUT_SCAN),
        "coupling_shape_reference_n_cut": COUPLING_SHAPE_REFERENCE_N_CUT,
        "coupling_scan": list(COUPLING_SCAN),
        "thresholds": THRESHOLDS,
    }
    config_hash = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return {
        "schema": "frost.physics.ds2-regional-markov-network-invariant.v1",
        "status": (
            "PASS_CANDIDATE_MARKOV_NETWORK_INVARIANT_BASELINE"
            if passed
            else "FAIL_CANDIDATE_MARKOV_NETWORK_INVARIANT_BASELINE"
        ),
        "qualification": {
            "threshold_status": "POST_EXPLORATORY_FROZEN_BEFORE_CI",
            "blinded_preregistration": False,
            "claim_level": "finite numerical candidate baseline",
        },
        "definition": {
            "network_invariant": (
                "sum_i I(site_i : site_i+2 | site_i+1) over adjacent triplets"
            ),
            "interpretation": (
                "quantum-Markov/recovery obstruction on a finite region-overlap chain"
            ),
            "is_spacetime_invariant": False,
            "is_global_gluing_law": False,
        },
        "configuration": config,
        "configuration_sha256": config_hash,
        "source_sha256": source_hashes(),
        "gates": gates,
        "gate_count": {"passed": sum(gates.values()), "total": len(gates)},
        "diagnostics": {
            "split_network_invariant_abs_max": split_abs_max,
            "full_network_invariant_by_n_cut": {
                str(k): v for k, v in full_by_cut.items()
            },
            "ncut_4_to_5_absolute_change": diff_45,
            "ncut_5_to_6_absolute_change": diff_56,
            "ncut_5_to_6_relative_change": rel_56,
            "successive_difference_contraction": contraction,
            "maximum_correlated_reflection_relative_difference": reflection_max,
            "local_unitary_invariance_absolute_defect": local_unitary_defect,
        },
        "scan": rows,
        "scope": {
            "validated_if_pass": (
                "finite dS2 four-site state-only quantum-Markov obstruction and "
                "cutoff-convergence trend"
            ),
            "continuum_factor_type": "BLOCKED_NOT_TESTED",
            "continuum_modular_inclusion": "BLOCKED_NOT_TESTED",
            "unique_global_gluing": "BLOCKED_NOT_TESTED",
            "spacetime_reconstruction": "BLOCKED_NOT_TESTED",
            "gravitational_dynamics": "BLOCKED_NOT_TESTED",
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("ds2-markov-network-invariant.json")
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = scan()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text)
    print(text, end="")
    if args.strict and not result["status"].startswith("PASS_"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
