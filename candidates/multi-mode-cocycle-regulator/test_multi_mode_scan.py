"""Regression tests for the bounded multi-mode cocycle/regulator harness."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).with_name("multi_mode_scan.py")
SPEC = importlib.util.spec_from_file_location("multi_mode_cocycle_regulator", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load multi_mode_scan.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class MultiModeRegulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MODULE.Config()

    def test_four_mode_finite_identities(self) -> None:
        metrics = MODULE.algebra_metrics(
            config=self.config,
            mode_count=4,
            frequencies=MODULE.BASE_FREQUENCIES,
        )
        self.assertGreater(metrics["minimum_density_eigenvalue"], 0.0)
        self.assertLess(metrics["maximum_unitarity_residual"], 1.0e-10)
        self.assertLess(metrics["maximum_chain_residual"], 1.0e-10)
        self.assertLess(metrics["maximum_transport_residual"], 1.0e-10)
        self.assertLess(metrics["maximum_modular_group_residual"], 1.0e-10)

    def test_factorization_control_and_interaction(self) -> None:
        metrics = MODULE.factorization_metrics(
            config=self.config,
            mode_count=3,
            frequencies=MODULE.BASE_FREQUENCIES[:3],
        )
        self.assertLess(metrics["uncoupled_factorization_residual"], 1.0e-8)
        self.assertGreater(metrics["coupled_nonfactorization_residual"], 1.0e-4)

    def test_regulated_readout_remains_nontrivial(self) -> None:
        metrics = MODULE.readout_metrics(
            config=self.config,
            mode_count=4,
            frequencies=MODULE.BASE_FREQUENCIES,
            t_ratio=2.0,
            eta_target=0.0625,
        )
        self.assertGreater(metrics["physical_modular_mismatch"], 1.0e-4)
        self.assertGreater(metrics["readout_modular_mismatch"], 1.0e-5)
        self.assertGreater(metrics["observable_retention"], 1.0e-4)
        self.assertLess(metrics["readout_cocycle_transport_residual"], 1.0e-9)

    def test_complete_bounded_gate(self) -> None:
        payload = MODULE.build_payload()
        self.assertEqual(
            payload["validation_summary"]["overall_status"],
            "PASS_BOUNDED_MULTI_MODE_REGULATOR_STRESS",
        )
        self.assertEqual(
            payload["metadata"]["continuum_connes_cocycle_status"],
            "BLOCKED_NOT_ESTABLISHED_BY_FINITE_MATRICES",
        )
        self.assertTrue(all(payload["validation_summary"]["gates"].values()))


if __name__ == "__main__":
    unittest.main()
