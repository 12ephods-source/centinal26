from __future__ import annotations

import math
import unittest

import numpy as np

import clock_regulator_scan as harness


class ClockRegulatorHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = harness.build_validation_payload()

    def test_liouvillian_and_observables_are_explicit_matrices(self) -> None:
        _, _, liouvillian, a_x, a_n = harness.oscillator_matrices(6, 1.0)
        self.assertEqual(liouvillian.shape, (36, 36))
        self.assertEqual(a_x.shape, (36, 36))
        self.assertEqual(a_n.shape, (36, 36))
        np.testing.assert_allclose(liouvillian, liouvillian.conj().T, atol=1.0e-14)
        np.testing.assert_allclose(a_x, a_x.conj().T, atol=1.0e-14)
        np.testing.assert_allclose(a_n, a_n.conj().T, atol=1.0e-14)

    def test_endpoint_free_povm_closes(self) -> None:
        povm = self.payload["baseline"]["povm"]
        self.assertLess(povm["R_POVM"], 1.0e-12)
        self.assertGreater(povm["lambda_min_E"], -1.0e-12)
        self.assertEqual(povm["N_tau"], 2 * povm["N_q"])

    def test_dense_and_compressed_evaluations_agree(self) -> None:
        crosscheck = self.payload["baseline"]["dense_matrix_crosscheck"]
        self.assertLess(crosscheck["maximum_absolute_discrepancy"], 1.0e-12)
        self.assertLess(crosscheck["dense_metrics"]["R_star_A_X"], 1.0e-12)
        self.assertLess(crosscheck["dense_metrics"]["R_star_A_N"], 1.0e-12)

    def test_fixed_delta_refinement_does_not_fake_improvement(self) -> None:
        baseline = self.payload["baseline"]["locked_delta_q_0.25"]
        half = self.payload["baseline"]["fixed_T_delta_q_half"]
        self.assertTrue(baseline["exact_lattice_resonance"])
        self.assertTrue(half["exact_lattice_resonance"])
        self.assertGreater(half["R_C_over_omega"], baseline["R_C_over_omega"])
        self.assertGreater(half["R_int_corrected"], baseline["R_int_corrected"])
        self.assertAlmostEqual(baseline["R_C_over_omega"], 0.00253748024486261, places=13)
        self.assertAlmostEqual(half["R_C_over_omega"], 0.047636473042011, places=13)

    def test_resolved_grid_avoids_all_stress_frequency_resonances(self) -> None:
        config = harness.HarnessConfig()
        averaging_width = 4.0 * config.beta
        intervals = harness.select_resolved_intervals(
            q_max=config.q_max,
            averaging_width=averaging_width,
            eta_target=0.0625,
        )
        delta_q = config.q_max / intervals
        self.assertLessEqual(averaging_width * delta_q, 0.0625)
        for omega in harness.FREQUENCIES:
            offset = abs(omega / delta_q - round(omega / delta_q))
            self.assertGreater(offset, 1.0e-10)

    def test_joint_scaling_and_false_positive_gates_pass(self) -> None:
        summary = self.payload["validation_summary"]
        self.assertEqual(summary["overall_status"], "PASS_CONTINUUM_REGULATOR_SCALING")
        self.assertTrue(all(summary["gates"].values()))
        self.assertLess(summary["maximum_continuum_R_C_relative_error"], 0.01)
        self.assertLess(summary["maximum_continuum_R_int_relative_error"], 0.01)
        self.assertLess(
            summary["coarse_to_resolved_R_C_ratio_at_T_over_beta_4"], 1.0e-5
        )

    def test_continuum_asymptotic_formulas(self) -> None:
        beta = 2.0 * math.pi
        prediction = harness.continuum_predictions(
            averaging_width=2.0 * beta,
            beta=beta,
            modular_parameter=0.25,
            omega=1.0,
        )
        self.assertAlmostEqual(
            prediction["R_C_over_omega"], 1.0 / (2.0 * math.sqrt(2.0) * beta)
        )
        expected_r_int = math.sqrt(2.0 * (1.0 - math.exp(-1.0 / 256.0)))
        self.assertAlmostEqual(prediction["R_int_corrected"], expected_r_int)

    def test_gate_does_not_overclaim_continuum_cocycle_physics(self) -> None:
        metadata = self.payload["metadata"]
        self.assertEqual(
            metadata["connes_cocycle_status"], "READY_FOR_FINITE_TYPE_I_COCYCLE_TEST"
        )
        self.assertFalse(metadata["continuum_cocycle_physics_validated"])
        self.assertEqual(metadata["classification"], "EXPERIMENTAL")


if __name__ == "__main__":
    unittest.main()

