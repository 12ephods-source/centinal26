import unittest

from scripts.ftoe_so10_protected_i_disposition_gate import evaluate


class ProtectedIDispositionGateTests(unittest.TestCase):
    def test_mandatory_fail_kills_current_candidate_for_admission(self):
        candidate = {
            "mandatory_admission_gates": {
                "collective_or_other_radiative_protection": "FAIL_CURRENT_MINIMAL_CANDIDATE",
                "representation_specific_C": "NOT_DERIVED",
            }
        }
        disposition = {
            "mandatory_failed_gate": "collective_or_other_radiative_protection",
            "scope_limit": "candidate-specific",
            "no_retuning": True,
        }
        result = evaluate(candidate, disposition)
        self.assertEqual(result["gate"], "FAIL_CURRENT_MINIMAL_CANDIDATE")
        self.assertEqual(result["downstream_candidate_work"], "STOP_AND_VERSION_SUCCESSOR")
        self.assertTrue(result["no_retuning"])

    def test_missing_declared_fail_is_inconsistent(self):
        candidate = {"mandatory_admission_gates": {"x": "NOT_DERIVED"}}
        disposition = {"mandatory_failed_gate": "x", "no_retuning": True}
        result = evaluate(candidate, disposition)
        self.assertEqual(result["gate"], "INCONSISTENT_DISPOSITION")


if __name__ == "__main__":
    unittest.main()
