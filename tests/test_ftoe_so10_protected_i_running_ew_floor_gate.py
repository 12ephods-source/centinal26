import unittest

from scripts.ftoe_so10_protected_i_running_ew_floor_gate import evaluate


class ProtectedIRunningEWFloorGateTests(unittest.TestCase):
    def test_rg_electroweak_floor_tightens_reference_envelope(self):
        contract = {
            "mu_I_GeV": 9540.0,
            "reference_lower_scale_bound_GeV": 188852.151,
            "admission_rule": "test",
            "scope_limit": "test",
            "primary_sources": ["arXiv:1201.5868", "arXiv:1308.1242"],
            "no_retuning": True,
        }
        result = evaluate(contract)
        self.assertEqual(result["gate"], "DERIVED_RUNNING_EW_FLOOR")
        self.assertAlmostEqual(result["cutoff_max_GeV"], 122559.40121128663, places=6)
        self.assertGreater(result["tightening_percent"], 35.0)
        self.assertLess(result["tightening_percent"], 35.2)
        self.assertGreater(result["target_to_cutoff_ratio"], 12.0)
        self.assertLess(result["target_to_cutoff_ratio"], 13.0)
        self.assertEqual(result["scientific_status"], "REVIEW")
        self.assertTrue(result["no_retuning"])


if __name__ == "__main__":
    unittest.main()
