from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "network_invariant_scan.py"
SPEC = importlib.util.spec_from_file_location("ds2_markov_network_invariant", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise ImportError(SOURCE)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class MarkovNetworkInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = MOD.scan()

    def test_all_frozen_gates_pass(self) -> None:
        self.assertTrue(all(self.result["gates"].values()), self.result["gates"])
        self.assertEqual(
            self.result["status"],
            "PASS_CANDIDATE_MARKOV_NETWORK_INVARIANT_BASELINE",
        )

    def test_split_control_is_markov(self) -> None:
        self.assertLessEqual(
            self.result["diagnostics"]["split_network_invariant_abs_max"],
            MOD.THRESHOLDS["split_network_invariant_abs_max"],
        )

    def test_geometry_network_is_nontrivial_and_monotone(self) -> None:
        self.assertTrue(self.result["gates"]["NET2_geometry_network_nontrivial"])
        self.assertTrue(self.result["gates"]["NET3_coupling_monotonicity"])

    def test_cutoff_refinement_contracts(self) -> None:
        diagnostics = self.result["diagnostics"]
        self.assertLessEqual(
            diagnostics["ncut_5_to_6_relative_change"],
            MOD.THRESHOLDS["ncut_5_to_6_relative_change_max"],
        )
        self.assertLessEqual(
            diagnostics["successive_difference_contraction"],
            MOD.THRESHOLDS["successive_difference_contraction_max"],
        )

    def test_local_unitary_invariance(self) -> None:
        self.assertLessEqual(
            self.result["diagnostics"]["local_unitary_invariance_absolute_defect"],
            MOD.THRESHOLDS["local_unitary_invariance_abs_max"],
        )

    def test_scope_and_qualification_remain_fail_closed(self) -> None:
        self.assertFalse(self.result["qualification"]["blinded_preregistration"])
        self.assertFalse(self.result["definition"]["is_spacetime_invariant"])
        self.assertFalse(self.result["definition"]["is_global_gluing_law"])
        for key in (
            "continuum_factor_type",
            "continuum_modular_inclusion",
            "unique_global_gluing",
            "spacetime_reconstruction",
            "gravitational_dynamics",
        ):
            self.assertEqual(self.result["scope"][key], "BLOCKED_NOT_TESTED")

    def test_invalid_inputs_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            MOD.chain_hamiltonian(1, 1.0)
        with self.assertRaises(ValueError):
            MOD.chain_hamiltonian(3, 1.1)
        with self.assertRaises(ValueError):
            MOD.partial_trace(np.eye(81), (), 3)


if __name__ == "__main__":
    unittest.main()
