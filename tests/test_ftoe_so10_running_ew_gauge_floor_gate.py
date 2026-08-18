import math
import unittest

from scripts.ftoe_so10_422_gate import M_I_PHYS, MU_I
from scripts.ftoe_so10_running_ew_gauge_floor_gate import (
    calculate,
    gauge_coefficient,
    residual,
    solve_break_even,
)


class TestRunningEWGaugeFloorGate(unittest.TestCase):
    def test_frozen_running_solution(self):
        r = calculate()
        self.assertAlmostEqual(r.cutoff_max_TeV, 122.55940121128663, places=9)
        self.assertAlmostEqual(r.g2_at_cutoff, 0.6155807303456179, places=13)
        self.assertAlmostEqual(r.gY_at_cutoff, 0.37272033502588064, places=13)
        self.assertAlmostEqual(r.C_gauge_at_cutoff, 0.9568045161452533, places=13)
        self.assertAlmostEqual(r.rg_shift_percent, 4.825104875147823, places=10)
        self.assertEqual(r.current_frozen_branch_status, "FAIL")
        self.assertEqual(r.scientific_gate_status, "FAIL")

    def test_implicit_break_even_identity(self):
        root = solve_break_even()
        _, _, _, _, coeff = gauge_coefficient(root)
        lhs = root * root * coeff / (16.0 * math.pi * math.pi)
        self.assertAlmostEqual(lhs / (MU_I * MU_I), 1.0, places=12)
        self.assertLess(abs(residual(root)) / (MU_I * MU_I), 1.0e-12)

    def test_threshold_is_below_break_even(self):
        r = calculate()
        self.assertGreater(r.cutoff_max_GeV, M_I_PHYS)
        self.assertGreater(r.gut_to_cutoff_ratio, 1.0e11)
        self.assertGreater(r.gut_scale_mass_correction_over_mu2, 1.0e22)

    def test_running_refines_but_does_not_remove_failure(self):
        r = calculate()
        self.assertGreater(r.cutoff_max_GeV, r.fixed_mz_cutoff_reference_GeV)
        self.assertLess(r.rg_shift_percent, 10.0)
        self.assertEqual(r.scientific_gate_status, "FAIL")

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            solve_break_even(mu_i=-1.0)
        with self.assertRaises(ValueError):
            solve_break_even(lo=1.0)
        with self.assertRaises(ValueError):
            calculate(gut_scale=0.0)


if __name__ == "__main__":
    unittest.main()
