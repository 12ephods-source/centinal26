import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ftoe_so10_422_gate.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_422_gate", MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

# Freeze the benchmark to the boundary conditions used in arXiv:2212.11315,
# Eq. (35), before judging the two-loop regression.
mod.MZ = 91.2
mod.ALPHA1_INV_MZ = 59.0272
mod.ALPHA2_INV_MZ = 29.5879
mod.ALPHA3_INV_MZ = 8.4678


class FToE422GateTests(unittest.TestCase):
    def test_extra_doublet_coefficients(self):
        self.assertAlmostEqual(mod.B_EXTRA_DOUBLEt["1"], 0.1, places=15)
        self.assertAlmostEqual(mod.B_EXTRA_DOUBLEt["2"], 1.0/6.0, places=15)
        self.assertEqual(mod.B_EXTRA_DOUBLEt["3"], 0.0)
        self.assertAlmostEqual(mod.B_2H["1"], 4.2, places=14)
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

    def test_reference_2hdm_two_loop_regression(self):
        mi, mu, alpha_u, inverse, spread = mod.solve_two_loop_422(threshold=mod.MZ)
        self.assertTrue(5e9 < mi < 5e10, f"reference MI={mi:.6e}")
        self.assertTrue(5e15 < mu < 5e16, f"reference MU={mu:.6e}")
        self.assertTrue(0.02 < alpha_u < 0.05, f"reference alphaU={alpha_u:.6e}")
        self.assertLess(spread, 5e-3, f"reference spread={spread:.6e}")

    def test_two_loop_piecewise_ftoe_solution_or_explicit_no_root(self):
        try:
            mi, mu, alpha_u, inverse, spread = mod.solve_two_loop_422()
        except ValueError as exc:
            # A no-root result is scientifically admissible, but must be explicit rather
            # than hidden by retuning.  Its interpretation is handled by calculate().
            self.assertIn("no sign change", str(exc))
            return
        self.assertGreater(mi, 1e6)
        self.assertLess(mi, 1e14)
        self.assertGreater(mu, mi)
        self.assertLess(mu, 1e19)
        self.assertTrue(0.0 < alpha_u < 0.1)
        self.assertLess(spread, 5e-3)
        self.assertTrue(all(v > 1.0 for v in inverse.values()))

    def test_beta_tail_reproduces_target_order(self):
        lambda_x, beta = mod.beta_tail()
        self.assertGreater(lambda_x, 1e11)
        self.assertLess(lambda_x, 1e12)
        self.assertTrue(0.5e-15 < beta < 2.0e-15)


if __name__ == "__main__":
    unittest.main()
