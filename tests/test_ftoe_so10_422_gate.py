import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = load_module("ftoe_so10_422_gate", ROOT / "scripts" / "ftoe_so10_422_gate.py")
roots2d = load_module(
    "ftoe_so10_422_2d_roots",
    ROOT / "scripts" / "ftoe_so10_422_2d_roots.py",
)

mod.MZ = 91.2
mod.ALPHA1_INV_MZ = 59.0272
mod.ALPHA2_INV_MZ = 29.5879
mod.ALPHA3_INV_MZ = 8.4678
roots2d.core.MZ = mod.MZ
roots2d.core.ALPHA1_INV_MZ = mod.ALPHA1_INV_MZ
roots2d.core.ALPHA2_INV_MZ = mod.ALPHA2_INV_MZ
roots2d.core.ALPHA3_INV_MZ = mod.ALPHA3_INV_MZ


class FToE422GateTests(unittest.TestCase):
    def test_extra_doublet_coefficients(self):
        self.assertAlmostEqual(mod.B_EXTRA_DOUBLEt["1"], 0.1, places=15)
        self.assertAlmostEqual(mod.B_EXTRA_DOUBLEt["2"], 1.0 / 6.0, places=15)
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

    def test_reference_2hdm_2d_solver_reproduces_published_branch(self):
        roots = roots2d.solve_all(threshold=roots2d.core.MZ, nx=3, ny=3)
        self.assertGreaterEqual(len(roots), 1)
        matches = [
            row
            for row in roots
            if abs(row["log10_MI"] - 10.03) < 0.25
            and abs(row["log10_MU"] - 16.19) < 0.25
        ]
        self.assertTrue(
            matches,
            f"roots={[(row['log10_MI'], row['log10_MU']) for row in roots]}",
        )
        branch = min(
            matches,
            key=lambda row: abs(row["log10_MI"] - 10.03)
            + abs(row["log10_MU"] - 16.19),
        )
        self.assertTrue(0.02 < branch["alpha_U"] < 0.05)
        self.assertLess(branch["max_spread"], 1e-4)

    def test_ftoe_threshold_2d_roots_are_explicit_and_finite(self):
        roots = roots2d.solve_all(threshold=roots2d.core.M_I_PHYS, nx=3, ny=3)
        for row in roots:
            self.assertGreater(row["MI_GeV"], 0.0)
            self.assertGreater(row["MU_GeV"], row["MI_GeV"])
            self.assertLess(row["MU_GeV"], 1e19)
            self.assertTrue(0.0 < row["alpha_U"] < 0.1)
            self.assertLess(row["max_spread"], 1e-4)

    def test_beta_tail_reproduces_target_order(self):
        lambda_x, beta = mod.beta_tail()
        self.assertGreater(lambda_x, 1e11)
        self.assertLess(lambda_x, 1e12)
        self.assertTrue(0.5e-15 < beta < 2.0e-15)


if __name__ == "__main__":
    unittest.main()
