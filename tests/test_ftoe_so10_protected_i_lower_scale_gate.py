import unittest

from scripts.ftoe_so10_protected_i_lower_scale_gate import evaluate


class ProtectedILowerScaleGateTests(unittest.TestCase):
    def test_reference_bound_is_derived_and_fail_closed(self):
        contract = {
            "mu_I_GeV": 9540.0,
            "alpha_reference": 0.032067325570772874,
            "coefficient_C_reference": 1.0,
            "scope_limit": "reference only",
            "no_retuning": True,
        }
        result = evaluate(contract)
        self.assertEqual(result["gate"], "DERIVED_REFERENCE_BOUND")
        self.assertGreater(result["break_even_f_GeV"], 1.0e5)
        self.assertLess(result["break_even_f_GeV"], 3.0e5)
        self.assertEqual(
            result["successor_status"],
            "REVIEW_REQUIRES_EXPLICIT_MECHANISM_AND_DERIVED_C",
        )
        self.assertTrue(result["no_retuning"])


if __name__ == "__main__":
    unittest.main()
