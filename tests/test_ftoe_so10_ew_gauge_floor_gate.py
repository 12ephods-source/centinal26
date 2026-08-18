import math
import unittest

from scripts.ftoe_so10_ew_gauge_floor_gate import calculate


class TestEWGaugeFloorGate(unittest.TestCase):
    def test_frozen_inputs(self):
        r = calculate()
        self.assertAlmostEqual(r.g2_mz, 0.6516770839735335, places=14)
        self.assertAlmostEqual(r.gY_mz, 0.3574520152502976, places=14)
        self.assertAlmostEqual(r.C_gauge, 1.0513657564014318, places=14)
        self.assertAlmostEqual(r.cutoff_max_TeV, 116.91798577951464, places=11)
        self.assertEqual(r.current_frozen_branch_status, "FAIL")
        self.assertEqual(r.scientific_gate_status, "FAIL")

    def test_cutoff_definition(self):
        r = calculate()
        lhs = (r.cutoff_max_GeV**2 / (16.0 * math.pi**2)) * r.C_gauge
        self.assertAlmostEqual(lhs / (r.mu_I_GeV**2), 1.0, places=13)

    def test_gut_scale_is_far_above_floor(self):
        r = calculate()
        self.assertGreater(r.gut_to_cutoff_ratio, 1.0e11)
        self.assertGreater(r.gut_scale_mass_correction_over_mu2, 1.0e22)

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            calculate(alpha1_inv=0.0)
        with self.assertRaises(ValueError):
            calculate(mu_i=-1.0)


if __name__ == "__main__":
    unittest.main()
