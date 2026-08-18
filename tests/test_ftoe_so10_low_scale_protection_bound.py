import math
import unittest

from scripts import ftoe_so10_low_scale_protection_bound as bound


class LowScaleProtectionBoundTests(unittest.TestCase):
    def test_reference_break_even_scale(self):
        result = bound.calculate()
        self.assertAlmostEqual(result.break_even_f_TeV, 188.85215118535442, places=9)
        self.assertEqual(result.reference_branch_status, "FAIL_ABOVE_BREAK_EVEN")

    def test_frozen_gut_scale_requires_extreme_coefficient_suppression(self):
        result = bound.calculate()
        self.assertAlmostEqual(result.max_C_at_frozen_MU, 8.487393224677035e-23, places=34)
        self.assertGreater(result.required_C_suppression_orders_at_frozen_MU, 22.0)

    def test_break_even_is_exact_for_declared_scaling(self):
        mu_i = 9.54e3
        alpha = 0.032067325570772874
        coefficient = 0.25
        f_scale = bound.break_even_scale(mu_i, alpha, coefficient)
        delta_m2 = coefficient * alpha / (4.0 * math.pi) * f_scale**2
        self.assertAlmostEqual(delta_m2, mu_i**2, places=4)

    def test_larger_scale_fails_declared_single_spurion_condition(self):
        mu_i = 9.54e3
        alpha = 0.032067325570772874
        f_scale = 2.0 * bound.break_even_scale(mu_i, alpha, 1.0)
        self.assertLess(bound.max_coefficient(mu_i, f_scale, alpha), 1.0)

    def test_lower_scale_branch_is_not_promoted(self):
        result = bound.calculate()
        self.assertEqual(result.lower_scale_branch_status, "REVIEW_REQUIRES_EXPLICIT_MECHANISM_AND_DERIVED_C")
        self.assertEqual(result.scientific_status, "REVIEW")


if __name__ == "__main__":
    unittest.main()
