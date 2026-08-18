import unittest

from scripts import ftoe_so10_protected_i_sequestering_gate as gate


class ProtectedISequesteringGateTests(unittest.TestCase):
    def test_reference_scale_is_below_G422_to_SM_matching(self):
        result = gate.calculate()
        self.assertEqual(result["gates"]["protected_sector_can_emerge_below_M_I"], "PASS")
        self.assertEqual(result["gates"]["elementary_SO10_irrep_embedding_required_by_scale"], "NO")
        self.assertLess(result["derived"]["f_max_over_M_I"], 1.0e-4)
        self.assertGreater(result["derived"]["separation_decades"], 4.0)

    def test_portal_matching_remains_fail_closed(self):
        result = gate.calculate()
        self.assertEqual(result["gates"]["SO10_to_protected_sector_portal_matching_derived"], "FAIL")
        self.assertEqual(result["gates"]["O_MU2_mass_backreaction_excluded"], "FAIL")
        self.assertEqual(result["scientific_status"], "REVIEW")

    def test_reference_bound_matches_existing_candidate_gate(self):
        f_max = gate.break_even_scale()
        self.assertAlmostEqual(f_max, 188852.15118535442, places=6)


if __name__ == "__main__":
    unittest.main()
