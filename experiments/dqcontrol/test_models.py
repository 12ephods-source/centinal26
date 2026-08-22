import unittest

from core import BenchConfig, attractor_trial, benchmark_all, phase_error_metrics


class TestDQControl(unittest.TestCase):
    def test_determinism(self):
        self.assertEqual(benchmark_all(), benchmark_all())

    def test_candidate_a_useful_high_structure(self):
        m = phase_error_metrics(BenchConfig(), 0.8)
        self.assertGreaterEqual(m["S_phi_candidate"], 1.20)

    def test_candidate_a_distinct_ar1_high_structure(self):
        m = phase_error_metrics(BenchConfig(), 0.8)
        self.assertGreaterEqual(m["relative_gain_vs_ar1"], 0.05)

    def test_candidate_a_null_not_catastrophic(self):
        m = phase_error_metrics(BenchConfig(), 0.0)
        self.assertGreaterEqual(m["S_phi_candidate"], 0.90)

    def test_candidate_b_contracts(self):
        m = attractor_trial(260822, False)
        self.assertLessEqual(m["contraction_ratio"], 0.50)

    def test_candidate_c_synergy(self):
        b = attractor_trial(260822, False)
        c = attractor_trial(260822, True)
        self.assertLessEqual(c["final_error"], 0.95 * b["final_error"])


if __name__ == "__main__":
    unittest.main()
