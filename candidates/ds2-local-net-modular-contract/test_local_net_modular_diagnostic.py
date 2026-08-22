from __future__ import annotations

import json
from pathlib import Path

import local_net_modular_diagnostic as diagnostic


def test_contract_is_fail_closed_about_operator_topology() -> None:
    contract = json.loads(Path("local_net_modular_contract.json").read_text())
    full_gate = contract["full_operator_topology_gate"]
    assert full_gate["status"] == "OPEN_NOT_ESTABLISHED_BY_THIS_CANDIDATE"
    assert "Type III_1 classification from finite-dimensional numerics" in contract[
        "forbidden_promotions"
    ]
    assert contract["next_gate_if_numerical_subgate_passes"] == (
        "COMMON_GNS_OR_STANDARD_SUBSPACE_OPERATOR_TOPOLOGY_CONVERGENCE"
    )


def test_smearing_supports_are_nested_as_declared() -> None:
    locality = diagnostic.locality_checks()
    assert locality["support_residual"] <= 1.0e-15
    assert locality["nested_region_membership_consistent"] is True
    membership = locality["region_membership"]
    assert membership["A_left"] == ["A", "B", "C"]
    assert membership["A_right"] == ["A", "B", "C"]
    assert membership["B_middle"] == ["B", "C"]
    assert membership["C_outer"] == ["C"]


def test_modular_evolution_preserves_reference_covariance() -> None:
    vectors = diagnostic.continuum_vectors(128)
    omegas = diagnostic.continuum_omegas(128)
    for vector in vectors.values():
        baseline = diagnostic.covariance(vector, vector, omegas)
        for s in diagnostic.MODULAR_S:
            evolved = diagnostic.modular_evolve(vector, omegas, s)
            after = diagnostic.covariance(evolved, evolved, omegas)
            assert abs(after - baseline) / max(1.0, abs(baseline)) <= 2.0e-12


def test_wrong_modular_direction_is_detected() -> None:
    assert diagnostic.wrong_modular_direction_gap() >= 1.0e-4


def test_diagnostic_passes_only_frozen_finite_family_subgate() -> None:
    result = diagnostic.evaluate()
    assert result["execution_pass"] is True
    assert result["scientific_pass"] is False
    assert result["status"] == "PASS_FROZEN_LOCAL_WEYL_MODULAR_CORRELATOR_SUBGATE"
    assert result["negative_control"]["detected"] is True
    interpretation = result["interpretation"]
    assert interpretation["promotion_ceiling"] == (
        "FROZEN_FINITE_TEST_FAMILY_NECESSARY_SUBGATE_ONLY"
    )
    assert interpretation["next_gate"] == (
        "COMMON_GNS_OR_STANDARD_SUBSPACE_OPERATOR_TOPOLOGY_CONVERGENCE"
    )
    assert "density of the finite smearing family in the local one-particle or Weyl test space" in interpretation[
        "not_established"
    ]
    assert "strong or weak operator convergence of the full local von Neumann net" in interpretation[
        "not_established"
    ]


def test_refinement_is_material_not_single_cutoff_coincidence() -> None:
    result = diagnostic.evaluate()
    refinement = result["lattice_refinement"]
    errors = refinement["errors"]
    assert len(errors) == len(diagnostic.LATTICE_SIZES)
    assert errors[-1] <= errors[0] / 20.0
    assert refinement["observed_order"] >= 1.5
    assert result["continuum_reference"]["max_512_to_1024_two_point_change"] <= 1.0e-8
