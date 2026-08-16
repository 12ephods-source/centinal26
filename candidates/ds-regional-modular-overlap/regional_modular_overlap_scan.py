"""Geometry-derived regional modular-inclusion/overlap falsification harness.

A three-site truncated scalar chain is built from the dS2 stretched-static-patch
finite-difference operator validated by the parent dS diamond harness.  Two
neighboring observer regions AB and BC share the nominal overlap B.  A split-state
control must preserve B under modular flow and admit an explicit state-preserving
conditional expectation.  The correlated geometry-derived thermal state is then
required to reveal, rather than hide, modular leakage from B.

This is a finite Type-I obstruction test.  It does not prove a continuum regional
algebra theorem, a Type-II/III classification, or global spacetime reconstruction.
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
N_SITE = 3
N_CUT = 3
X_MAX = 4.0
S_SCAN = (-0.25, -0.125, 0.125, 0.25)
COUPLING_SCAN = (0.0, 0.25, 0.5, 0.75, 1.0)
THRESH = {
    "matrix": 1.0e-10,
    "split_leakage": 1.0e-10,
    "expectation": 1.0e-10,
    "mutual_information": 1.0e-5,
    "correlated_leakage": 1.0e-5,
    "mirror_relative": 1.0e-8,
    "faithful_min_eigenvalue": 1.0e-14,
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


DS = load_parent_module(
    "ds_diamond_relational_parent",
    "ds-diamond-relational-harness/ds_diamond_relational_scan.py",
)


def annihilation(n: int) -> np.ndarray:
    a = np.zeros((n, n), dtype=complex)
    for k in range(1, n):
        a[k - 1, k] = np.sqrt(k)
    return a


def kron_all(factors: list[np.ndarray]) -> np.ndarray:
    result = np.array([[1.0 + 0.0j]])
    for factor in factors:
        result = np.kron(result, factor)
    return result


def embed_local(op: np.ndarray, site: int) -> np.ndarray:
    identity = np.eye(N_CUT, dtype=complex)
    return kron_all([op if i == site else identity for i in range(N_SITE)])


def qp_operators() -> tuple[list[np.ndarray], list[np.ndarray]]:
    a = annihilation(N_CUT)
    q_local = (a + a.conj().T) / np.sqrt(2.0)
    p_local = 1j * (a.conj().T - a) / np.sqrt(2.0)
    return (
        [embed_local(q_local, i) for i in range(N_SITE)],
        [embed_local(p_local, i) for i in range(N_SITE)],
    )


def geometry_kernel(coupling_fraction: float) -> np.ndarray:
    if not 0.0 <= coupling_fraction <= 1.0:
        raise ValueError("coupling_fraction must be in [0,1]")
    kernel = DS.laplacian_matrix(N_SITE, x_max=X_MAX)
    diagonal = np.diag(np.diag(kernel))
    return diagonal + coupling_fraction * (kernel - diagonal)


def chain_hamiltonian(coupling_fraction: float) -> np.ndarray:
    q_ops, p_ops = qp_operators()
    kernel = geometry_kernel(coupling_fraction)
    dim = N_CUT**N_SITE
    h = np.zeros((dim, dim), dtype=complex)
    for p in p_ops:
        h += 0.5 * (p @ p)
    for i in range(N_SITE):
        for j in range(N_SITE):
            h += 0.5 * kernel[i, j] * (q_ops[i] @ q_ops[j])
    return 0.5 * (h + h.conj().T)


def thermal(h: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh(h)
    weights = np.exp(-BETA * (vals - np.min(vals)))
    weights /= np.sum(weights)
    return (vecs * weights) @ vecs.conj().T


def spectral_map(rho: np.ndarray, fn) -> np.ndarray:
    vals, vecs = np.linalg.eigh(0.5 * (rho + rho.conj().T))
    if np.min(vals) <= 0.0:
        raise FloatingPointError("faithful state required")
    return (vecs * fn(vals)) @ vecs.conj().T


def rho_it(rho: np.ndarray, s: float) -> np.ndarray:
    return spectral_map(rho, lambda x: np.exp(1j * s * np.log(x)))


def modular_flow(rho: np.ndarray, s: float, observable: np.ndarray) -> np.ndarray:
    unitary = rho_it(rho, s)
    return unitary @ observable @ unitary.conj().T


def partial_trace(rho: np.ndarray, keep: tuple[int, ...]) -> np.ndarray:
    dims = [N_CUT] * N_SITE
    trace = tuple(i for i in range(N_SITE) if i not in keep)
    n = len(dims)
    permutation = list(keep) + list(trace) + [i + n for i in keep] + [
        i + n for i in trace
    ]
    tensor = rho.reshape(dims + dims).transpose(permutation)
    d_keep = N_CUT ** len(keep)
    d_trace = N_CUT ** len(trace)
    tensor = tensor.reshape(d_keep, d_trace, d_keep, d_trace)
    return np.einsum("atbt->ab", tensor)


def entropy(rho: np.ndarray) -> float:
    vals = np.linalg.eigvalsh(0.5 * (rho + rho.conj().T))
    vals = vals[vals > 1.0e-15]
    return float(-np.sum(vals * np.log(vals)))


def mutual_information_ab(rho_ab: np.ndarray) -> float:
    # Here rho_ab lives on two N_CUT-dimensional sites.
    tensor = rho_ab.reshape(N_CUT, N_CUT, N_CUT, N_CUT)
    rho_a = np.einsum("abcb->ac", tensor)
    rho_b = np.einsum("abad->bd", tensor)
    return entropy(rho_a) + entropy(rho_b) - entropy(rho_ab)


def local_x() -> np.ndarray:
    a = annihilation(N_CUT)
    return (a + a.conj().T) / np.sqrt(2.0)


def project_ab_to_b_subalgebra(matrix: np.ndarray) -> np.ndarray:
    tensor = matrix.reshape(N_CUT, N_CUT, N_CUT, N_CUT)
    tr_a = np.einsum("abad->bd", tensor)
    return np.kron(np.eye(N_CUT) / N_CUT, tr_a)


def project_bc_to_b_subalgebra(matrix: np.ndarray) -> np.ndarray:
    tensor = matrix.reshape(N_CUT, N_CUT, N_CUT, N_CUT)
    tr_c = np.einsum("abcb->ac", tensor)
    return np.kron(tr_c, np.eye(N_CUT) / N_CUT)


def leakage_metrics(rho_ab: np.ndarray, rho_bc: np.ndarray) -> dict[str, float]:
    x = local_x()
    b_in_ab = np.kron(np.eye(N_CUT), x)
    b_in_bc = np.kron(x, np.eye(N_CUT))
    leak_ab: list[float] = []
    leak_bc: list[float] = []
    for s in S_SCAN:
        flowed_ab = modular_flow(rho_ab, s, b_in_ab)
        flowed_bc = modular_flow(rho_bc, s, b_in_bc)
        leak_ab.append(
            float(
                np.linalg.norm(flowed_ab - project_ab_to_b_subalgebra(flowed_ab), "fro")
                / np.linalg.norm(flowed_ab, "fro")
            )
        )
        leak_bc.append(
            float(
                np.linalg.norm(flowed_bc - project_bc_to_b_subalgebra(flowed_bc), "fro")
                / np.linalg.norm(flowed_bc, "fro")
            )
        )
    maximum_ab = max(leak_ab)
    maximum_bc = max(leak_bc)
    mirror_relative = abs(maximum_ab - maximum_bc) / max(
        maximum_ab, maximum_bc, 1.0e-30
    )
    return {
        "AB_max_relative_modular_leakage": maximum_ab,
        "BC_max_relative_modular_leakage": maximum_bc,
        "mirror_relative_difference": mirror_relative,
    }


def split_expectation_metrics(rho_full: np.ndarray) -> dict[str, float]:
    rho_ab = partial_trace(rho_full, (0, 1))
    rho_a = partial_trace(rho_full, (0,))
    rng = np.random.default_rng(20260816)
    x = rng.normal(size=(N_CUT**2, N_CUT**2)) + 1j * rng.normal(
        size=(N_CUT**2, N_CUT**2)
    )
    x = x + x.conj().T

    def expectation(matrix: np.ndarray) -> np.ndarray:
        tensor = matrix.reshape(N_CUT, N_CUT, N_CUT, N_CUT)
        b = np.einsum("ca,abcd->bd", rho_a, tensor)
        return np.kron(np.eye(N_CUT), b)

    ex = expectation(x)
    state_defect = abs(np.trace(rho_ab @ x) - np.trace(rho_ab @ ex))
    idempotence = np.linalg.norm(expectation(ex) - ex, "fro")
    b1 = rng.normal(size=(N_CUT, N_CUT)) + 1j * rng.normal(
        size=(N_CUT, N_CUT)
    )
    b2 = rng.normal(size=(N_CUT, N_CUT)) + 1j * rng.normal(
        size=(N_CUT, N_CUT)
    )
    left_input = np.kron(np.eye(N_CUT), b1) @ x @ np.kron(np.eye(N_CUT), b2)
    left = expectation(left_input)
    right = np.kron(np.eye(N_CUT), b1) @ ex @ np.kron(np.eye(N_CUT), b2)
    bimodule = np.linalg.norm(left - right, "fro")
    return {
        "state_preservation_defect": float(state_defect),
        "idempotence_defect": float(idempotence),
        "bimodule_defect": float(bimodule),
    }


def scan() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for fraction in COUPLING_SCAN:
        h = chain_hamiltonian(fraction)
        rho = thermal(h)
        rho_ab = partial_trace(rho, (0, 1))
        rho_bc = partial_trace(rho, (1, 2))
        row: dict[str, Any] = {
            "coupling_fraction": fraction,
            "full_state_min_eigenvalue": float(np.min(np.linalg.eigvalsh(rho))),
            "rho_AB_min_eigenvalue": float(np.min(np.linalg.eigvalsh(rho_ab))),
            "rho_BC_min_eigenvalue": float(np.min(np.linalg.eigvalsh(rho_bc))),
            "mutual_information_AB": mutual_information_ab(rho_ab),
        }
        row.update(leakage_metrics(rho_ab, rho_bc))
        rows.append(row)

    split_rho = thermal(chain_hamiltonian(0.0))
    expectation = split_expectation_metrics(split_rho)
    split = rows[0]
    physical = rows[-1]
    gates = {
        "REG1_split_state_modular_inclusion": max(
            split["AB_max_relative_modular_leakage"],
            split["BC_max_relative_modular_leakage"],
        )
        <= THRESH["split_leakage"],
        "REG2_split_state_conditional_expectation": max(expectation.values())
        <= THRESH["expectation"],
        "REG3_geometry_state_is_correlated": physical["mutual_information_AB"]
        >= THRESH["mutual_information"],
        "REG4_geometry_state_obstructs_naive_overlap_inclusion": min(
            physical["AB_max_relative_modular_leakage"],
            physical["BC_max_relative_modular_leakage"],
        )
        >= THRESH["correlated_leakage"],
        "REG5_reflection_symmetric_obstruction": physical["mirror_relative_difference"]
        <= THRESH["mirror_relative"],
        "REG6_all_states_faithful": min(
            min(row["full_state_min_eigenvalue"] for row in rows),
            min(row["rho_AB_min_eigenvalue"] for row in rows),
            min(row["rho_BC_min_eigenvalue"] for row in rows),
        )
        >= THRESH["faithful_min_eigenvalue"],
    }
    config = {
        "beta_dS": float(BETA),
        "N_site": N_SITE,
        "N_cut": N_CUT,
        "x_max": X_MAX,
        "coupling_scan": list(COUPLING_SCAN),
        "modular_parameters": list(S_SCAN),
        "thresholds": THRESH,
    }
    config_sha = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    parent_path = CANDIDATES / "ds-diamond-relational-harness/ds_diamond_relational_scan.py"
    parent_sha = hashlib.sha256(parent_path.read_bytes()).hexdigest()
    passed = all(gates.values())
    return {
        "schema_version": 1,
        "status": (
            "PASS_DS2_REGIONAL_MODULAR_OVERLAP_OBSTRUCTION_BASELINE"
            if passed
            else "FAIL_DS2_REGIONAL_MODULAR_OVERLAP_OBSTRUCTION_BASELINE"
        ),
        "scope": {
            "validated": (
                "finite geometry-derived A-B-C chain: split-state modular inclusion/"
                "conditional expectation control and correlated-state modular leakage"
            ),
            "continuum_regional_algebra_theorem": "BLOCKED_NOT_TESTED",
            "Type_II_or_Type_III_classification": "BLOCKED_NOT_TESTED",
            "global_spacetime_gluing": "BLOCKED_NOT_TESTED",
        },
        "configuration": config,
        "configuration_sha256": config_sha,
        "source_sha256": source_sha,
        "parent_source_sha256": parent_sha,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "geometry_kernel_full": geometry_kernel(1.0).tolist(),
        "scan": rows,
        "split_conditional_expectation": expectation,
        "gates": gates,
        "gate_count": {"passed": sum(gates.values()), "total": len(gates)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("regional-overlap.json"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = scan()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.strict and not result["status"].startswith("PASS_"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
