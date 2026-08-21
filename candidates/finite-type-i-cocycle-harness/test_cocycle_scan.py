#!/usr/bin/env python3
"""Regression tests for the finite Type-I cocycle consistency harness."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

import numpy as np

MODULE_PATH = pathlib.Path(__file__).with_name("cocycle_scan.py")
SPEC = importlib.util.spec_from_file_location("finite_type_i_cocycle_scan", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load cocycle_scan.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CocycleHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MODULE.CocycleConfig()

    def test_support_aware_density_phase_is_unitary(self) -> None:
        model = MODULE.state_pair(
            n_cut=self.config.n_cut,
            omega=1.03,
            beta=self.config.beta,
            perturbation_strength=0.05,
        )
        phase = MODULE.density_phase(model["rho1"], 0.25)
        identity = np.eye(self.config.n_cut, dtype=complex)
        residual = MODULE.relative_frobenius(phase.conj().T @ phase, identity)
        self.assertLess(residual, 1.0e-12)

    def test_finite_type_i_cocycle_chain_rule(self) -> None:
        metrics = MODULE.finite_cocycle_metrics(
            config=self.config,
            omega=1.03,
            perturbation_strength=0.05,
        )
        self.assertGreater(metrics["rho0_min_eigenvalue"], 0.0)
        self.assertGreater(metrics["rho1_min_eigenvalue"], 0.0)
        self.assertLess(metrics["maximum_cocycle_chain_residual"], 1.0e-11)
        self.assertLess(metrics["maximum_state_transport_residual"], 1.0e-11)

    def test_zero_perturbation_control(self) -> None:
        metrics = MODULE.cocycle_readout_metrics(
            config=self.config,
            omega=1.03,
            perturbation_strength=0.0,
            t_ratio=2.0,
            eta_target=0.0625,
        )
        self.assertLess(metrics["physical_modular_mismatch"], 1.0e-11)
        self.assertLess(metrics["readout_modular_mismatch"], 1.0e-11)
        self.assertLess(metrics["readout_cocycle_transport_residual"], 1.0e-10)

    def test_nontrivial_perturbation_survives_readout(self) -> None:
        metrics = MODULE.cocycle_readout_metrics(
            config=self.config,
            omega=1.01,
            perturbation_strength=0.05,
            t_ratio=2.0,
            eta_target=0.0625,
        )
        self.assertGreater(metrics["physical_modular_mismatch"], 1.0e-4)
        self.assertGreater(metrics["readout_modular_mismatch"], 1.0e-5)
        self.assertGreater(metrics["reference_observable_retention"], 1.0e-4)
        self.assertGreater(metrics["perturbed_observable_retention"], 1.0e-4)
        self.assertFalse(metrics["exact_lattice_resonance"])

    def test_full_line_projection_leakage_is_real_and_cutoff_sensitive(self) -> None:
        coarse = MODULE.full_line_projection_metric(
            q_max=4.0,
            delta_q=self.config.projection_delta_q,
            displacement=-1.03,
            sigma_q=self.config.projection_sigma_q,
        )
        fine = MODULE.full_line_projection_metric(
            q_max=10.0,
            delta_q=self.config.projection_delta_q,
            displacement=-1.03,
            sigma_q=self.config.projection_sigma_q,
        )
        self.assertLess(coarse["translation_norm_error"], 1.0e-12)
        self.assertLess(fine["translation_norm_error"], 1.0e-12)
        self.assertGreater(coarse["post_translation_negative_probability"], 1.0e-6)
        self.assertLess(
            fine["post_translation_negative_probability"],
            coarse["post_translation_negative_probability"] * 1.0e-4,
        )

    def test_complete_strict_gate(self) -> None:
        payload = MODULE.build_validation_payload()
        self.assertEqual(
            payload["validation_summary"]["overall_status"],
            "PASS_FINITE_TYPE_I_COCYCLE_CONSISTENCY",
        )
        self.assertEqual(
            payload["metadata"]["continuum_connes_cocycle_status"],
            "BLOCKED_NOT_ESTABLISHED_BY_FINITE_MATRICES",
        )
        self.assertTrue(all(payload["validation_summary"]["gates"].values()))


if __name__ == "__main__":
    unittest.main()
