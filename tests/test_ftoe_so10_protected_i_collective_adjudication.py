import unittest

from scripts.ftoe_so10_protected_i_collective_adjudication import evaluate


class ProtectedICollectiveAdjudicationTests(unittest.TestCase):
    def test_current_minimal_candidate_fails_closed(self):
        candidate = {
            "schema": "FTOE-PROTECTED-I-CANDIDATE-v0.2",
            "mechanism_class": "nonlinear_composite_pNGB",
        }
        result = evaluate(candidate)
        self.assertEqual(result["gate"], "FAIL_CURRENT_MINIMAL_CANDIDATE")
        self.assertFalse(any(result["checks"].values()))
        self.assertTrue(result["no_retuning"])

    def test_populated_collective_structure_is_not_preemptively_failed(self):
        candidate = {
            "schema": "TEST",
            "mechanism_class": "collective_test",
            "collective_breaking_couplings": ["g1", "g2"],
            "symmetry_restoration_tests": ["g1->0 restores G1", "g2->0 restores G2"],
            "partner_states": ["W_prime"],
            "one_loop_cancellation_proof": "derived",
            "radiative_mass_bound": {"delta_m2_over_mu2": 0.5},
        }
        result = evaluate(candidate)
        self.assertEqual(result["gate"], "COLLECTIVE_PROTECTION_STRUCTURALLY_SPECIFIED")


if __name__ == "__main__":
    unittest.main()
