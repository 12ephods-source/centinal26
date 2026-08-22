"""Finite common-state G2 topology reconstruction falsification harness.

The reconstruction path receives only a density matrix and local Hilbert dimension.
The latent regulator lattice is withheld until scoring. No matter observable,
Einstein equation, Newton normalization, entropy-area law, or target edge is used to
construct the candidate topology.

A PASS is deliberately narrow: the finite state contains enough correlation
structure to recover a path adjacency/topological-distance surrogate under the
frozen scans. It is not a spacetime metric or gravitational-dynamics result.
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
N_SITE = 4
N_CUT_SCAN = (3, 4, 5)
COUPLING_SCAN = (0.10, 0.25, 0.50, 1.0)
TARGET_EDGES = frozenset({(0, 1), (1, 2), (2, 3)})
PERMUTATION = (2, 0, 3, 1)
THRESHOLDS = {
    "signal_floor": 1.0e-8,
    "neighbor_non_neighbor_ratio_min": 1.5,
    "local_unitary_mi_absolute_defect_max": 1.0e-10,
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


NETWORK = load_parent_module(
    "ds2_markov_network_parent",
    "ds-regional-markov-network-invariant/network_invariant_scan.py",
)


def canonical_edge(i: int, j: int) -> tuple[int, int]:
    if i == j:
        raise ValueError("self-edge is invalid")
    return (i, j) if i < j else (j, i)


def pairwise_mutual_information(rho: np.ndarray, n_cut: int) -> np.ndarray:
    expected_dim = n_cut**N_SITE
    if rho.shape != (expected_dim, expected_dim):
        raise ValueError("rho dimension does not match n_cut and N_SITE")
    if n_cut < 2:
        raise ValueError("n_cut must be >=2")

    one_site_entropy = [
        NETWORK.entropy(NETWORK.partial_trace(rho, (i,), n_cut))
        for i in range(N_SITE)
    ]
    matrix = np.zeros((N_SITE, N_SITE), dtype=float)
    for i in range(N_SITE):
        for j in range(i + 1, N_SITE):
            rho_ij = NETWORK.partial_trace(rho, (i, j), n_cut)
            value = one_site_entropy[i] + one_site_entropy[j] - NETWORK.entropy(rho_ij)
            if value < -1.0e-10:
                raise FloatingPointError("mutual information negative beyond tolerance")
            matrix[i, j] = matrix[j, i] = max(float(value), 0.0)
    return matrix


def all_weighted_edges(mi: np.ndarray) -> list[tuple[float, int, int]]:
    if mi.shape != (N_SITE, N_SITE):
        raise ValueError("unexpected mutual-information matrix shape")
    return [
        (float(mi[i, j]), i, j)
        for i in range(N_SITE)
        for j in range(i + 1, N_SITE)
    ]


def maximum_spanning_tree(mi: np.ndarray) -> frozenset[tuple[int, int]]:
    """Kruskal maximum spanning tree using state-derived weights only."""
    parent = list(range(N_SITE))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> bool:
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        parent[rb] = ra
        return True

    selected: set[tuple[int, int]] = set()
    for weight, i, j in sorted(all_weighted_edges(mi), key=lambda row: (-row[0], row[1], row[2])):
        del weight
        if union(i, j):
            selected.add((i, j))
        if len(selected) == N_SITE - 1:
            break
    if len(selected) != N_SITE - 1:
        raise RuntimeError("unable to construct spanning tree")
    return frozenset(selected)


def top_edge_oracle(mi: np.ndarray) -> frozenset[tuple[int, int]]:
    """Independent recomputation: choose the top N-1 MI edges without cycle logic."""
    ranked = sorted(all_weighted_edges(mi), key=lambda row: (-row[0], row[1], row[2]))
    return frozenset((i, j) for _, i, j in ranked[: N_SITE - 1])


def reconstruct_topology(rho: np.ndarray, n_cut: int) -> dict[str, Any]:
    """Reconstruct without access to target lattice geometry."""
    mi = pairwise_mutual_information(rho, n_cut)
    max_signal = float(np.max(mi))
    if max_signal <= THRESHOLDS["signal_floor"]:
        return {
            "status": "ABSTAIN_UNINFORMATIVE_STATE",
            "pairwise_mutual_information": mi.tolist(),
            "max_mutual_information": max_signal,
            "edges": [],
            "top_edge_oracle": [],
            "graph_distance": None,
        }

    mst = maximum_spanning_tree(mi)
    oracle = top_edge_oracle(mi)
    distances = graph_distance_matrix(mst)
    return {
        "status": "CANDIDATE_TOPOLOGY",
        "pairwise_mutual_information": mi.tolist(),
        "max_mutual_information": max_signal,
        "edges": [list(edge) for edge in sorted(mst)],
        "top_edge_oracle": [list(edge) for edge in sorted(oracle)],
        "graph_distance": distances.tolist(),
    }


def graph_distance_matrix(edges: frozenset[tuple[int, int]]) -> np.ndarray:
    distance = np.full((N_SITE, N_SITE), np.inf, dtype=float)
    np.fill_diagonal(distance, 0.0)
    for i, j in edges:
        distance[i, j] = distance[j, i] = 1.0
    for k in range(N_SITE):
        for i in range(N_SITE):
            for j in range(N_SITE):
                candidate = distance[i, k] + distance[k, j]
                if candidate < distance[i, j]:
                    distance[i, j] = candidate
    if not np.all(np.isfinite(distance)):
        raise RuntimeError("reconstructed graph is disconnected")
    return distance


def target_distance_matrix() -> np.ndarray:
    indices = np.arange(N_SITE)
    return np.abs(indices[:, None] - indices[None, :]).astype(float)


def edge_set_from_result(result: dict[str, Any], key: str = "edges") -> frozenset[tuple[int, int]]:
    return frozenset(canonical_edge(int(i), int(j)) for i, j in result[key])


def separation_ratio(mi: np.ndarray) -> float:
    true_weights = [mi[i, j] for i, j in TARGET_EDGES]
    non_edges = [
        (i, j)
        for i in range(N_SITE)
        for j in range(i + 1, N_SITE)
        if (i, j) not in TARGET_EDGES
    ]
    false_weights = [mi[i, j] for i, j in non_edges]
    denominator = max(max(false_weights), 1.0e-300)
    return float(min(true_weights) / denominator)


def permute_sites(rho: np.ndarray, n_cut: int, permutation: tuple[int, ...]) -> np.ndarray:
    if tuple(sorted(permutation)) != tuple(range(N_SITE)):
        raise ValueError("permutation must contain each site exactly once")
    tensor = rho.reshape([n_cut] * (2 * N_SITE))
    axes = list(permutation) + [site + N_SITE for site in permutation]
    return tensor.transpose(axes).reshape(rho.shape)


def permuted_target_edges(permutation: tuple[int, ...]) -> frozenset[tuple[int, int]]:
    inverse = {old: new for new, old in enumerate(permutation)}
    return frozenset(
        canonical_edge(inverse[i], inverse[j]) for i, j in TARGET_EDGES
    )


def deterministic_local_phase_vector(n_cut: int) -> np.ndarray:
    local = [
        np.exp(1j * np.linspace(0.0, phase, n_cut))
        for phase in (0.17, -0.31, 0.43, -0.59)
    ]
    vector = local[0]
    for factor in local[1:]:
        vector = np.kron(vector, factor)
    return vector


def apply_product_local_phase(rho: np.ndarray, n_cut: int) -> np.ndarray:
    phase = deterministic_local_phase_vector(n_cut)
    return phase[:, None] * rho * np.conj(phase)[None, :]


def physical_state(n_cut: int, coupling_fraction: float) -> np.ndarray:
    h = NETWORK.chain_hamiltonian(n_cut, coupling_fraction)
    return NETWORK.REGIONAL.thermal(h)


def source_hashes() -> dict[str, str]:
    paths = {
        "this_source": Path(__file__).resolve(),
        "network_parent": CANDIDATES
        / "ds-regional-markov-network-invariant/network_invariant_scan.py",
        "regional_parent": CANDIDATES
        / "ds-regional-modular-overlap/regional_modular_overlap_scan.py",
        "geometry_parent": CANDIDATES
        / "ds-diamond-relational-harness/ds_diamond_relational_scan.py",
    }
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths.items()
    }


def run() -> dict[str, Any]:
    target_distance = target_distance_matrix()
    cutoff_rows: dict[str, Any] = {}
    cutoff_exact = True
    distance_exact = True
    oracle_agrees = True
    minimum_separation = float("inf")

    for n_cut in N_CUT_SCAN:
        rho = physical_state(n_cut, 1.0)
        reconstruction = reconstruct_topology(rho, n_cut)
        mi = np.asarray(reconstruction["pairwise_mutual_information"], dtype=float)
        edges = edge_set_from_result(reconstruction)
        oracle = edge_set_from_result(reconstruction, "top_edge_oracle")
        graph_distance = np.asarray(reconstruction["graph_distance"], dtype=float)
        ratio = separation_ratio(mi)
        minimum_separation = min(minimum_separation, ratio)
        cutoff_exact &= edges == TARGET_EDGES
        distance_exact &= np.array_equal(graph_distance, target_distance)
        oracle_agrees &= oracle == edges
        cutoff_rows[str(n_cut)] = {
            "reconstruction": reconstruction,
            "neighbor_non_neighbor_separation_ratio": ratio,
            "target_match_used_only_for_scoring": edges == TARGET_EDGES,
            "distance_match_used_only_for_scoring": bool(
                np.array_equal(graph_distance, target_distance)
            ),
        }

    split_rho = physical_state(4, 0.0)
    split = reconstruct_topology(split_rho, 4)

    coupling_rows: list[dict[str, Any]] = []
    coupling_robust = True
    for coupling in COUPLING_SCAN:
        rho = physical_state(4, coupling)
        reconstructed = reconstruct_topology(rho, 4)
        edges = edge_set_from_result(reconstructed)
        coupling_robust &= edges == TARGET_EDGES
        coupling_rows.append(
            {
                "coupling_fraction": coupling,
                "status": reconstructed["status"],
                "edges": reconstructed["edges"],
                "target_match_used_only_for_scoring": edges == TARGET_EDGES,
            }
        )

    rho4 = physical_state(4, 1.0)
    permuted = permute_sites(rho4, 4, PERMUTATION)
    permuted_result = reconstruct_topology(permuted, 4)
    permuted_edges = edge_set_from_result(permuted_result)
    expected_permuted_edges = permuted_target_edges(PERMUTATION)
    permutation_equivariant = permuted_edges == expected_permuted_edges

    mi_original = pairwise_mutual_information(rho4, 4)
    phased = apply_product_local_phase(rho4, 4)
    mi_phased = pairwise_mutual_information(phased, 4)
    local_unitary_defect = float(np.max(np.abs(mi_original - mi_phased)))
    phased_result = reconstruct_topology(phased, 4)
    local_unitary_topology_same = edge_set_from_result(phased_result) == TARGET_EDGES

    gates = {
        "G2A_cutoff_stable_adjacency_reconstruction": cutoff_exact,
        "G2B_cutoff_stable_graph_distance_reconstruction": distance_exact,
        "G2C_independent_edge_oracle_agreement": oracle_agrees,
        "G2D_discriminatory_neighbor_separation": minimum_separation
        >= THRESHOLDS["neighbor_non_neighbor_ratio_min"],
        "G2E_split_state_abstention": split["status"]
        == "ABSTAIN_UNINFORMATIVE_STATE",
        "G2F_nonzero_coupling_robustness": coupling_robust,
        "G2G_site_permutation_equivariance": permutation_equivariant,
        "G2H_product_local_unitary_invariance": local_unitary_defect
        <= THRESHOLDS["local_unitary_mi_absolute_defect_max"]
        and local_unitary_topology_same,
    }
    passed = all(gates.values())

    configuration = {
        "N_site": N_SITE,
        "N_cut_scan": list(N_CUT_SCAN),
        "coupling_scan": list(COUPLING_SCAN),
        "permutation": list(PERMUTATION),
        "thresholds": THRESHOLDS,
        "target_edges_scoring_only": [list(edge) for edge in sorted(TARGET_EDGES)],
    }
    config_hash = hashlib.sha256(
        json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return {
        "schema": "frost.physics.common-state-geometry-g2-topology.v1",
        "status": (
            "PASS_G2_FINITE_TOPOLOGY_RECONSTRUCTION_CANDIDATE"
            if passed
            else "FAIL_G2_FINITE_TOPOLOGY_RECONSTRUCTION_CANDIDATE"
        ),
        "qualification": {
            "class": "CONFIRMATORY_FINITE_ENGINEERING_GATE",
            "blinded_scientific_preregistration": False,
            "target_used_by_reconstruction_algorithm": False,
        },
        "definition": {
            "state_to_geometry_map": (
                "rho -> pairwise mutual information -> maximum-weight spanning tree "
                "-> graph geodesic distance"
            ),
            "reconstructed_object": "finite unlabeled adjacency/topological distance",
            "spacetime_metric_claim": False,
            "proper_length_claim": False,
            "causal_structure_claim": False,
        },
        "configuration": configuration,
        "configuration_sha256": config_hash,
        "source_sha256": source_hashes(),
        "gates": gates,
        "gate_count": {"passed": sum(gates.values()), "total": len(gates)},
        "diagnostics": {
            "minimum_neighbor_non_neighbor_separation_ratio": minimum_separation,
            "split_max_mutual_information": split["max_mutual_information"],
            "local_unitary_mi_absolute_defect": local_unitary_defect,
            "permuted_expected_edges": [
                list(edge) for edge in sorted(expected_permuted_edges)
            ],
            "permuted_reconstructed_edges": permuted_result["edges"],
        },
        "cutoff_scan": cutoff_rows,
        "coupling_robustness_scan": coupling_rows,
        "split_control": split,
        "scope": {
            "finite_topological_geometry": "QUALIFIED_IF_PASS",
            "continuum_state_to_spacetime_dictionary": "BLOCKED_NOT_TESTED",
            "metric_scale": "BLOCKED_NOT_TESTED",
            "lorentzian_causal_structure": "BLOCKED_NOT_TESTED",
            "continuum_factor_type": "BLOCKED_NOT_TESTED",
            "G3_matter_geometry_cross_channel": "BLOCKED_NOT_TESTED",
            "G4_gravitational_dynamics": "BLOCKED_NOT_TESTED",
            "G5_planck_scale_consequences": "BLOCKED_NOT_TESTED",
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
        "--output", type=Path, default=Path("g2-finite-topology-reconstruction.json")
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = run()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text)
    print(text, end="")
    if args.strict and not result["status"].startswith("PASS_"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
