from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("phase1_kms_bkm_harness", HERE / "harness.py")
assert SPEC is not None and SPEC.loader is not None
harness = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = harness
SPEC.loader.exec_module(harness)


class Phase1RegulatedKMSBKMTests(unittest.TestCase):
    def test_fixed_dimensional_normalization(self) -> None:
        self.assertEqual(harness.L, 1.0)
        self.assertAlmostEqual(harness.BETA, 2.0 * np.pi * harness.L)
        report = harness.run_harness()
        self.assertEqual(report["analytic_normalization"]["beta_dS_formula"], "2*pi*L")
        self.assertFalse(report["analytic_normalization"]["fitted_constants"])

    def test_deterministic_schema_contract(self) -> None:
        report = harness.run_harness()
        self.assertEqual(
            report["schema"],
            "frost.phase1.regulated-kms-modular-cocycle-falsification.v2",
        )
        self.assertEqual(report["determinism"]["seed"], 0)
        self.assertFalse(report["determinism"]["randomness_used"])
        self.assertEqual(report["determinism"]["json_keys"], "sorted")

    def test_reference_kms_and_modular_flow(self) -> None:
        result = harness.reference_scan()
        self.assertLess(result["kms_boundary_residual"], 1.0e-10)
        self.assertLess(
            result["thermal_modular_static_intertwining_max_residual"], 1.0e-10
        )
        self.assertLess(result["normalized_trace_modular_flow_max_residual"], 1.0e-10)

    def test_finite_type_i_cocycle(self) -> None:
        result = harness.cocycle_scan()
        self.assertFalse(result["continuum_claim"])
        self.assertLess(result["maximum_algebraic_residual"], 1.0e-10)
        self.assertLess(result["maximum_generator_relative_error"], 1.0e-7)

    def test_bkm_is_analytic_and_regulator_convergent(self) -> None:
        result = harness.bkm_scan()
        self.assertFalse(result["normalization_fitted"])
        self.assertLess(result["maximum_energy_identity_absolute_error"], 1.0e-11)
        self.assertLess(result["n_cut_6_max_bkm_relative_error"], 1.0e-7)
        self.assertLess(
            result["epsilon_0.05_to_0.025_refinement_relative_change"], 1.0e-7
        )
        self.assertLess(result["n_cut_5_to_6_refinement_relative_change"], 1.0e-7)

    def test_gate_scope_blocks_overpromotion(self) -> None:
        report = harness.run_harness()
        gate4 = report["gate_accounting"][
            "Gate_4_Relative_Entropy_BKM_Matter_Energy_Baseline"
        ]
        self.assertEqual(gate4["definition_status"], "CANONICALIZED_IN_SCHEMA_V2")
        self.assertEqual(report["gate_accounting"]["Gate_5"], "PROPOSED")
        self.assertEqual(report["gate_accounting"]["Gate_6"], "PROPOSED")
        self.assertIn("emergent geometry", report["scope"]["not_established"])
        self.assertIn(
            "BKM-Hollands-Wald canonical-energy equivalence",
            report["scope"]["not_established"],
        )

    def test_strict_status(self) -> None:
        report = harness.run_harness()
        self.assertEqual(
            report["status"],
            "PASS_REGULATED_KMS_MODULAR_COCYCLE_BKM_BASELINE",
        )
        self.assertTrue(all(report["gates"].values()))


if __name__ == "__main__":
    unittest.main()
