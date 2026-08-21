"""Regression tests for the two-mode finite Type-I cocycle stress harness."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).with_name("two_mode_scan.py")
SPEC = importlib.util.spec_from_file_location("two_mode_cocycle_stress", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load two_mode_scan.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TwoModeStressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MODULE.TwoModeConfig()

    def test_interacting_state_remains_faithful(self) -> None:
        metrics = MODULE.finite_two_mode_cocycle_metrics(
            config=self.config,
            omega_1=1.03,
            omega_2=1.41,
            interaction_strength=self.config.interaction_strength,
        )
        self.assertGreater(metrics["rho0_min_eigenvalue"], 0.0)
        self.assertGreater(metrics["rho1_min_eigenvalue"], 0.0)
        self.assertLess(metrics["maximum_cocycle_chain_residual"], 1.0e-10)
        self.assertLess(metrics["maximum_state_transport_residual"], 1.0e-10)

    def test_uncoupled_factorization_and_coupled_breaking(self) -> None:
        metrics = MODULE.factorization_metrics(
            config=self.config,
            omega_1=1.01,
            omega_2=1.37,
        )
        self.assertLess(metrics["uncoupled_factorization_residual"], 1.0e-10)
        self.assertGreater(metrics["coupled_nonfactorization_residual"], 1.0e-4)

    def test_resolved_two_mode_readout_is_nontrivial(self) -> None:
        metrics = MODULE.two_mode_readout_metrics(
            config=self.config,
            omega_1=1.01,
            omega_2=1.37,
            t_ratio=2.0,
            eta_target=0.0625,
        )
        self.assertFalse(metrics["exact_lattice_resonance"])
        self.assertGreater(metrics["physical_modular_mismatch"], 1.0e-4)
        self.assertGreater(metrics["readout_modular_mismatch"], 1.0e-5)
        self.assertGreater(metrics["observable_retention"], 1.0e-4)
        self.assertLess(metrics["readout_cocycle_transport_residual"], 1.0e-9)

    def test_complete_two_mode_gate(self) -> None:
        payload = MODULE.build_validation_payload()
        self.assertEqual(
            payload["validation_summary"]["overall_status"],
            "PASS_TWO_MODE_FINITE_TYPE_I_STRESS",
        )
        self.assertEqual(
            payload["metadata"]["continuum_connes_cocycle_status"],
            "BLOCKED_NOT_ESTABLISHED_BY_FINITE_MATRICES",
        )
        self.assertTrue(all(payload["validation_summary"]["gates"].values()))


if __name__ == "__main__":
    unittest.main()
