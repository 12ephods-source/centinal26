import importlib.util
import math
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ftoe_so10_422_gate.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_422_gate", MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class FToE422GateTests(unittest.TestCase):
    def test_extra_doublet_coefficients(self):
        self.assertAlmostEqual(mod.B_EXTRA_DOUBLEt["1"], 0.1, places=15)
        self.assertAlmostEqual(mod.B_EXTRA_DOUBLEt["2"], 1.0/6.0, places=15)
        self.assertEqual(mod.B_EXTRA_DOUBLEt["3"], 0.0)
        self.assertAlmostEqual(mod.B_2H["1"], 4.2, places=15)
        self.assertAlmostEqual(mod.B_2H["2"], -3.0, places=15)

    def test_intermediate_root_is_residual_certified(self):
        mi = mod.bisect_log_root(mod.ps_matching_residual, 1e8, 1e14)
        self.assertLess(abs(mod.ps_matching_residual(mi)), 1e-9)
        self.assertGreater(mi, 1e9)
        self.assertLess(mi, 1e13)

    def test_422_unifies_all_three_couplings_at_one_loop(self):
        mi = mod.bisect_log_root(mod.ps_matching_residual, 1e8, 1e14)
        mu, alpha_u, inverse = mod.solve_422_unification(mi)
        self.assertGreater(mu, mi)
        self.assertGreater(alpha_u, 0.0)
        self.assertLess(max(inverse.values()) - min(inverse.values()), 1e-8)

    def test_beta_tail_reproduces_target_order(self):
        lambda_x, beta = mod.beta_tail()
        self.assertGreater(lambda_x, 1e11)
        self.assertLess(lambda_x, 1e12)
        self.assertTrue(0.5e-15 < beta < 2.0e-15)

    def test_gate_fails_closed_on_unfinished_science(self):
        result = mod.calculate()
        self.assertEqual(result.scientific_status, "REVIEW")
        self.assertEqual(result.gates["FToE_specific_two_loop_running"], "NOT_TESTED")
        self.assertEqual(result.gates["full_heavy_threshold_spectrum"], "NOT_TESTED")
        self.assertEqual(result.gates["proton_decay_from_frozen_spectrum"], "NOT_TESTED")


if __name__ == "__main__":
    unittest.main()
