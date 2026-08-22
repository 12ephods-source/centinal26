from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "ds_diamond_relational_scan.py"
SPEC = importlib.util.spec_from_file_location("ds_diamond_relational_scan", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise ImportError(SOURCE)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class DeSitterDiamondRelationalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = MOD.run()

    def test_static_patch_coordinate_identity(self) -> None:
        geometry = self.result["geometry"]
        self.assertLessEqual(
            geometry["metric_coordinate_identity_residual"],
            MOD.THRESH["metric_identity"],
        )

    def test_lattice_spectrum_matches_matrix(self) -> None:
        geometry = self.result["geometry"]
        self.assertLessEqual(
            geometry["matrix_vs_closed_form_spectrum_max_relative_residual"],
            MOD.THRESH["matrix_spectrum"],
        )

    def test_lattice_modes_converge_second_order(self) -> None:
        geometry = self.result["geometry"]
        self.assertLessEqual(
            geometry["final_max_mode_relative_error"],
            MOD.THRESH["final_mode_relative_error"],
        )
        self.assertGreaterEqual(
            geometry["minimum_successive_error_reduction_ratio"],
            MOD.THRESH["convergence_ratio"],
        )

    def test_geometry_mode_preserves_kms_and_cocycle_baseline(self) -> None:
        algebra = self.result["geometry_mode_kms_cocycle"]
        self.assertLessEqual(algebra["kms_boundary_residual"], MOD.THRESH["kms"])
        self.assertLessEqual(
            algebra["reference_modular_to_static_flow_max_residual"],
            MOD.THRESH["kms"],
        )
        self.assertLessEqual(
            algebra["cocycle_and_unitarity_max_residual"], MOD.THRESH["cocycle"]
        )
        self.assertLessEqual(
            algebra["cocycle_modular_intertwining_max_residual"],
            MOD.THRESH["cocycle"],
        )

    def test_regulated_relational_map_converges(self) -> None:
        rel = self.result["regulated_relational_embedding"]
        self.assertTrue(rel["constraint_residual_strictly_decreases_with_T"])
        self.assertTrue(rel["intertwining_residual_strictly_decreases_with_T"])
        self.assertFalse(rel["any_exact_lattice_resonance"])
        self.assertLessEqual(
            rel["final_max_R_C_continuum_relative_error"],
            MOD.THRESH["relational_continuum_relative_error"],
        )
        self.assertLessEqual(
            rel["final_max_R_int_continuum_relative_error"],
            MOD.THRESH["relational_continuum_relative_error"],
        )

    def test_clock_povm_gate(self) -> None:
        povm = self.result["regulated_relational_embedding"]["clock_povm"]
        self.assertLessEqual(povm["R_POVM"], MOD.THRESH["clock_closure"])
        self.assertGreaterEqual(
            povm["lambda_min_E"], MOD.THRESH["clock_min_eigenvalue"]
        )

    def test_scope_remains_fail_closed(self) -> None:
        scope = self.result["scope"]
        self.assertEqual(scope["continuum_Type_III_to_Type_II_claim"], "BLOCKED_NOT_TESTED")
        self.assertEqual(scope["gravitational_canonical_energy"], "BLOCKED_NOT_TESTED")
        self.assertEqual(scope["Einstein_reconstruction"], "BLOCKED_NOT_TESTED")
        self.assertFalse(
            self.result["regulated_relational_embedding"]["is_claimed_continuum_embedding"]
        )

    def test_all_strict_gates_pass(self) -> None:
        self.assertTrue(all(self.result["gates"].values()), self.result["gates"])
        self.assertEqual(
            self.result["status"], "PASS_DS2_DIAMOND_REGULATED_RELATIONAL_BASELINE"
        )


if __name__ == "__main__":
    unittest.main()
