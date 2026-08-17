import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

mod = load_module("ftoe_so10_422_gate", ROOT / "scripts" / "ftoe_so10_422_gate.py")
scan = load_module("ftoe_so10_422_branch_scan", ROOT / "scripts" / "ftoe_so10_422_branch_scan.py")

# Primary-paper Eq. (35) boundary conditions.
mod.MZ = 91.2
mod.ALPHA1_INV_MZ = 59.0272
mod.ALPHA2_INV_MZ = 29.5879
mod.ALPHA3_INV_MZ = 8.4678
scan.core.MZ = mod.MZ
scan.core.ALPHA1_INV_MZ = mod.ALPHA1_INV_MZ
scan.core.ALPHA2_INV_MZ = mod.ALPHA2_INV_MZ
scan.core.ALPHA3_INV_MZ = mod.ALPHA3_INV_MZ


class FToE422GateTests(unittest.TestCase):
    def test_extra_doublet_coefficients(self):
        self.assertAlmostEqual(mod.B_EXTRA_DOUBLEt["1"], 0.1, places=15)
        self.assertAlmostEqual(mod.B_EXTRA_DOUBLEt["2"], 1.0/6.0, places=15)
        self.assertEqual(mod.B_EXTRA_DOUBLEt["3"], 0.0)
        self.assertAlmostEqual(mod.B_2H["1"], 4.2, places=14)
        self.assertAlmostEqual(mod.B_2H["2"], -3.0, places=15)

    def test_one_loop_intermediate_root_is_residual_certified(self):
        mi = mod.bisect_log_root(mod.ps_matching_residual, 1e8, 1e14)
        self.assertLess(abs(mod.ps_matching_residual(mi)), 1e-9)
        self.assertGreater(mi, 1e9)
        self.assertLess(mi, 1e13)

    def test_one_loop_422_unifies_all_three_couplings(self):
        mi = mod.bisect_log_root(mod.ps_matching_residual, 1e8, 1e14)
        mu, alpha_u, inverse = mod.solve_422_unification(mi)
        self.assertGreater(mu, mi)
        self.assertGreater(alpha_u, 0.0)
        self.assertLess(max(inverse.values()) - min(inverse.values()), 1e-8)

    def test_reference_2hdm_scan_contains_published_branch(self):
        rows = scan.solve_branches(threshold=scan.core.MZ, samples=400)
        self.assertGreaterEqual(len(rows), 1)
        matches = [r for r in rows if abs(r["log10_MI"] - 10.03) < 0.35 and abs(r["log10_MU"] - 16.19) < 0.35]
        self.assertTrue(matches, f"branches={[(r['log10_MI'], r['log10_MU']) for r in rows]}")
        branch = min(matches, key=lambda r: abs(r["log10_MI"]-10.03)+abs(r["log10_MU"]-16.19))
        self.assertTrue(0.02 < branch["alpha_U"] < 0.05)
        self.assertLess(branch["max_spread"], 5e-3)

    def test_ftoe_threshold_scan_is_explicit_and_finite(self):
        rows = scan.solve_branches(threshold=scan.core.M_I_PHYS, samples=400)
        for row in rows:
            self.assertGreater(row["MI_GeV"], 0.0)
            self.assertGreater(row["MU_GeV"], row["MI_GeV"])
            self.assertLess(row["MU_GeV"], 1e19)
            self.assertTrue(0.0 < row["alpha_U"] < 0.1)
            self.assertLess(row["max_spread"], 5e-3)

    def test_beta_tail_reproduces_target_order(self):
        lambda_x, beta = mod.beta_tail()
        self.assertGreater(lambda_x, 1e11)
        self.assertLess(lambda_x, 1e12)
        self.assertTrue(0.5e-15 < beta < 2.0e-15)


if __name__ == "__main__":
    unittest.main()
