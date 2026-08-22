from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "phase1_bkm_independent_oracle", HERE / "independent_bkm_oracle.py"
)
assert SPEC is not None and SPEC.loader is not None
oracle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = oracle
SPEC.loader.exec_module(oracle)


class IndependentBKMOracleTests(unittest.TestCase):
    def test_oracle_passes_all_fail_closed_gates(self) -> None:
        report = oracle.run()
        self.assertEqual(report["status"], "PASS_INDEPENDENT_BKM_ORACLE")
        self.assertTrue(all(report["gates"].values()))
        self.assertFalse(report["scope"]["continuum_claim"])

    def test_relative_entropy_path_is_independent_of_matrix_log_rho_epsilon(self) -> None:
        p = oracle.thermal_probabilities(6, 1.0)
        g = oracle.generator(6, 0.31 + 0.17j)
        u = oracle.unitary_from_generator(g, 0.05)
        value = oracle.relative_entropy_eigenbasis(p, u)
        self.assertGreater(value, 0.0)

    def test_divided_difference_and_fd_agree(self) -> None:
        report = oracle.run()
        self.assertLessEqual(
            report["diagnostics"]["max_fd_relative_error_vs_divided_difference"],
            oracle.THRESHOLDS["fd_vs_divided_difference_relative"],
        )

    def test_negative_controls_are_decisively_rejected(self) -> None:
        report = oracle.run()
        self.assertGreaterEqual(
            report["diagnostics"]["minimum_negative_control_relative_separation"],
            oracle.THRESHOLDS["negative_control_min_relative_separation"],
        )

    def test_frequency_weighting_stress_fixture(self) -> None:
        report = oracle.run()
        self.assertLessEqual(
            report["diagnostics"]["stress_fixture_correct_relative_error"],
            oracle.THRESHOLDS["n7_vs_analytic_relative"],
        )
        self.assertGreater(
            report["diagnostics"]["stress_fixture_frequency_blind_relative_separation"],
            0.25,
        )

    def test_invalid_inputs_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            oracle.thermal_probabilities(4, 0.0)
        with self.assertRaises(ValueError):
            oracle.annihilation(1)


if __name__ == "__main__":
    unittest.main()
