import json
import unittest

from scripts import ftoe_so10_protected_i_candidate_gate as gate


class ProtectedICandidateGateTests(unittest.TestCase):
    def test_current_candidate_fails_closed(self):
        result = gate.evaluate(gate.load_candidate())
        self.assertEqual(result["candidate_admission"], "FAIL_CURRENT_CANDIDATE")
        self.assertEqual(result["gates"]["explicit_nonlinear_coset"], "PASS")
        self.assertEqual(result["gates"]["I_doublet_identification"], "PASS")
        self.assertEqual(result["gates"]["reference_bound_reproduced"], "PASS")
        self.assertEqual(result["gates"]["protection_scale_frozen"], "FAIL")
        self.assertEqual(result["gates"]["renormalizable_SO10_portal_suppression"], "FAIL")
        self.assertEqual(result["gates"]["beta_function_backreaction"], "FAIL")

    def test_synthetic_fully_closed_candidate_can_pass_structure(self):
        candidate = json.loads(json.dumps(gate.load_candidate()))
        candidate["protection_scale_f_GeV"] = 1.0e5
        for key in (
            "gauge_embedding_and_hypercharge",
            "collective_or_other_radiative_protection",
            "representation_specific_C",
            "renormalizable_SO10_portal_suppression",
            "strong_sector_resonance_spectrum",
            "beta_function_backreaction",
            "matching_to_existing_mu_I_and_G422_branch",
        ):
            candidate["mandatory_admission_gates"][key] = "DERIVED"
        result = gate.evaluate(candidate)
        self.assertEqual(result["candidate_admission"], "PASS")

    def test_reference_bound_rejects_scale_above_break_even(self):
        candidate = json.loads(json.dumps(gate.load_candidate()))
        candidate["protection_scale_f_GeV"] = 2.0e5
        result = gate.evaluate(candidate)
        self.assertEqual(result["gates"]["protection_scale_frozen"], "PASS")
        self.assertEqual(result["gates"]["protection_scale_within_reference_bound"], "FAIL")


if __name__ == "__main__":
    unittest.main()
