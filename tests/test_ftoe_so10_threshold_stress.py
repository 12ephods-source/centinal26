import importlib.util
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "ftoe_so10_threshold_stress.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_threshold_stress", PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class ThresholdStressTests(unittest.TestCase):
    def test_prefactor_boundary_scales_as_mu_four(self):
        k1 = mod.decay_prefactor_limit_geV5(1.0e16, 0.03)
        k2 = mod.decay_prefactor_limit_geV5(2.0e16, 0.03)
        self.assertAlmostEqual(k2 / k1, 16.0, places=12)

    def test_prefactor_boundary_scales_inverse_alpha_squared(self):
        k1 = mod.decay_prefactor_limit_geV5(1.0e16, 0.03)
        k2 = mod.decay_prefactor_limit_geV5(1.0e16, 0.06)
        self.assertAlmostEqual(k2 / k1, 0.25, places=12)

    def test_prefactor_boundary_rejects_nonpositive_inputs(self):
        with self.assertRaises(ValueError):
            mod.decay_prefactor_limit_geV5(0.0, 0.03)
        with self.assertRaises(ValueError):
            mod.decay_prefactor_limit_geV5(1.0e16, -0.03)

    def test_sweep_records_every_predeclared_point_without_silent_skip(self):
        calls = []

        def fake_solver(alpha_s, threshold):
            calls.append((alpha_s, threshold))
            shift = 1.0 + 0.1 * (alpha_s - 0.118) + 1e-7 * math.log(threshold)
            mu = 2.0e16 * shift
            alpha_u = 0.032 * shift
            inverse = {"4": 31.25, "L": 31.25, "R": 31.25}
            return 7.0e9, mu, alpha_u, inverse, 0.0

        alphas = (0.117, 0.119)
        factors = (0.5, 1.0, 2.0)
        result = mod.run_sweep(
            alpha_s_values=alphas,
            threshold_factors=factors,
            solver=fake_solver,
        )
        self.assertEqual(result["gate"], "PASS_STRESS_EXECUTION")
        self.assertEqual(result["point_count"], len(alphas) * len(factors))
        self.assertEqual(result["failure_count"], 0)
        self.assertEqual(len(calls), len(alphas) * len(factors))
        self.assertTrue(
            all("max_decay_prefactor_GeV5_at_limit" in row for row in result["points"])
        )
        self.assertTrue(
            all("reduced_scale_ratio_to_baseline" in row for row in result["points"])
        )

    def test_sweep_fails_closed_if_any_grid_point_does_not_solve(self):
        def fake_solver(alpha_s, threshold):
            if alpha_s > 0.118:
                raise ValueError("synthetic no-root")
            return (
                7.0e9,
                2.0e16,
                0.032,
                {"4": 31.0, "L": 31.0, "R": 31.0},
                0.0,
            )

        result = mod.run_sweep(
            alpha_s_values=(0.117, 0.119),
            threshold_factors=(1.0,),
            solver=fake_solver,
        )
        self.assertEqual(result["gate"], "FAIL_STRESS_EXECUTION")
        self.assertEqual(result["point_count"], 1)
        self.assertEqual(result["failure_count"], 1)
        self.assertIn("synthetic no-root", result["failures"][0]["error"])


if __name__ == "__main__":
    unittest.main()
