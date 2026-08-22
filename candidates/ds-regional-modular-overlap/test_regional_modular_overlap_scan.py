from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "regional_modular_overlap_scan.py"
SPEC = importlib.util.spec_from_file_location("regional_modular_overlap_scan", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise ImportError(SOURCE)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class RegionalModularOverlapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = MOD.scan()
        cls.split = cls.result["scan"][0]
        cls.physical = cls.result["scan"][-1]

    def test_split_state_preserves_overlap(self) -> None:
        self.assertLessEqual(
            self.split["AB_max_relative_modular_leakage"],
            MOD.THRESH["split_leakage"],
        )
        self.assertLessEqual(
            self.split["BC_max_relative_modular_leakage"],
            MOD.THRESH["split_leakage"],
        )

    def test_split_conditional_expectation(self) -> None:
        metrics = self.result["split_conditional_expectation"]
        self.assertLessEqual(max(metrics.values()), MOD.THRESH["expectation"])

    def test_geometry_state_is_correlated(self) -> None:
        self.assertGreaterEqual(
            self.physical["mutual_information_AB"],
            MOD.THRESH["mutual_information"],
        )

    def test_correlations_generate_modular_leakage(self) -> None:
        self.assertGreaterEqual(
            self.physical["AB_max_relative_modular_leakage"],
            MOD.THRESH["correlated_leakage"],
        )
        self.assertGreaterEqual(
            self.physical["BC_max_relative_modular_leakage"],
            MOD.THRESH["correlated_leakage"],
        )
        self.assertGreater(
            self.physical["AB_max_relative_modular_leakage"],
            self.split["AB_max_relative_modular_leakage"],
        )

    def test_reflection_symmetry(self) -> None:
        self.assertLessEqual(
            self.physical["mirror_relative_difference"],
            MOD.THRESH["mirror_relative"],
        )

    def test_fail_closed_scope(self) -> None:
        scope = self.result["scope"]
        self.assertEqual(scope["continuum_regional_algebra_theorem"], "BLOCKED_NOT_TESTED")
        self.assertEqual(scope["Type_II_or_Type_III_classification"], "BLOCKED_NOT_TESTED")
        self.assertEqual(scope["global_spacetime_gluing"], "BLOCKED_NOT_TESTED")

    def test_all_gates_pass(self) -> None:
        self.assertTrue(all(self.result["gates"].values()), self.result["gates"])
        self.assertEqual(
            self.result["status"],
            "PASS_DS2_REGIONAL_MODULAR_OVERLAP_OBSTRUCTION_BASELINE",
        )


if __name__ == "__main__":
    unittest.main()
