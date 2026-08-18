import unittest

from scripts.ftoe_so10_linear_symmetry_no_go import certificate


class LinearSymmetryNoGoTests(unittest.TestCase):
    def test_norm_portal_is_certified_invariant(self):
        result = certificate()
        self.assertEqual(result.ordinary_linear_internal_symmetry_status, "FAIL")
        self.assertEqual(result.phase_ZN_status, "FAIL")
        self.assertIn("(I^dagger I)(Phi^dagger Phi)", result.portal)

    def test_non_linear_branches_are_not_overclaimed(self):
        result = certificate()
        self.assertEqual(result.nonlinear_shift_or_collective_status, "REVIEW")
        self.assertEqual(result.sequestered_or_supersymmetric_status, "REVIEW")
        self.assertEqual(result.scientific_status, "REVIEW")


if __name__ == "__main__":
    unittest.main()
