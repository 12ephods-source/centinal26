#!/usr/bin/env python3
import unittest

import toe_engine


class CandidateToEEngineTests(unittest.TestCase):
    def setUp(self):
        self.cases = toe_engine.regression_cases()

    def test_historical_phase3_fails(self):
        case = self.cases["historical_phase3_failure"]
        self.assertEqual(case["verdict"], "FAIL")
        self.assertEqual(case["gates"]["G4_INFLATION"], "FAIL")

    def test_minimal_dark_portal_fails(self):
        case = self.cases["historical_dark_failure"]
        self.assertEqual(case["verdict"], "FAIL")
        self.assertEqual(case["gates"]["G5_DARK"], "FAIL")

    def test_bounce_as_written_fails(self):
        case = self.cases["historical_bounce_failure"]
        self.assertEqual(case["verdict"], "FAIL")
        self.assertEqual(case["gates"]["G8_COSMOLOGY"], "FAIL")

    def test_gate2b_survives_only_as_review(self):
        case = self.cases["best_current_composite"]
        self.assertEqual(case["gates"]["G4_INFLATION"], "REVIEW")
        self.assertNotEqual(case["verdict"], "FAIL")
        self.assertFalse(case["certification_permitted"])

    def test_certification_firewall(self):
        for candidate in toe_engine.enumerate_candidates()[:25]:
            self.assertNotEqual(candidate["verdict"], "VERIFIED")
            self.assertFalse(candidate["certification_permitted"])

    def test_default_generation_excludes_falsified_components(self):
        registry = toe_engine.load_registry()
        index = toe_engine.index_components(registry)
        for candidate in toe_engine.enumerate_candidates():
            for sector, component_id in candidate["genome"].items():
                self.assertFalse(index[sector][component_id].get("hard_fail", False))

    def test_generation_is_deterministic(self):
        first = [candidate["candidate_id"] for candidate in toe_engine.enumerate_candidates()]
        second = [candidate["candidate_id"] for candidate in toe_engine.enumerate_candidates()]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
