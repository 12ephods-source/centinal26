import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


op = load("ftoe_so10_operator_gate_test", ROOT / "scripts" / "ftoe_so10_operator_gate.py")
th = load("ftoe_so10_threshold_gate_test", ROOT / "scripts" / "ftoe_so10_threshold_gate.py")


class OperatorGateTests(unittest.TestCase):
    def test_phase_symmetry_never_forbids_norm_bilinear(self):
        for n in range(2, 40):
            for q in range(n):
                self.assertEqual(op.neutral_bilinear_charge(q, n), 0)

    def test_shared_yukawa_higgs_forces_cubic_neutral(self):
        for n in range(2, 40):
            for q16 in range(n):
                row = op.same_higgs_no_go(n, q16)
                self.assertTrue(row["cubic_forced_allowed"])
                self.assertEqual(row["q_10_126_210"], 0)

    def test_Z11_selector_delays_B3_Sk_tower_to_dimension_13(self):
        # q(B3)=q(S)=1 -> 1+k=0 mod 11 first at k=10 -> dimension 13.
        self.assertEqual(op.first_allowed_spurion_power(11, 1, 1), 10)
        rows = op.selector_search(13, n_max=11)
        self.assertTrue(any(r["N"] == 11 and r["q_B3"] == 1 and r["q_S"] == 1 for r in rows))

    def test_current_two_loop_MU_prefers_order_one_n9(self):
        result = op.calculate(2.04990990688745e16)
        self.assertEqual(result.preferred_power, 9)
        self.assertEqual(result.preferred_operator_dimension, 13)
        self.assertTrue(0.1 < result.preferred_coefficient_times_Ceff < 10.0)
        self.assertEqual(result.scientific_status, "REVIEW")
        self.assertEqual(result.gates["actual_Clebsch_factor_Ceff"], "NOT_TESTED")


class ThresholdGateTests(unittest.TestCase):
    def test_zero_log_thresholds_leave_couplings_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "spectrum.json"
            p.write_text(json.dumps({"multiplets": [
                {"name": "A", "mass_GeV": 1e16, "beta": {"4": 1.0, "L": 2.0, "R": 3.0}}
            ]}))
            spectrum = th.load_spectrum(p)
            delta = th.threshold_corrections(spectrum, 1e16)
            for value in delta.values():
                self.assertAlmostEqual(value, 0.0, places=15)

    def test_synthetic_frozen_spectrum_correction_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "spectrum.json"
            p.write_text(json.dumps({"multiplets": [
                {"name": "A", "mass_GeV": 2e16, "beta": {"4": 1.0, "L": 0.0, "R": -1.0}},
                {"name": "B", "mass_GeV": 0.5e16, "beta": {"4": -0.5, "L": 1.0, "R": 0.0}}
            ]}))
            a = th.threshold_corrections(th.load_spectrum(p), 1e16)
            b = th.threshold_corrections(th.load_spectrum(p), 1e16)
            self.assertEqual(a, b)
            self.assertEqual(set(a), {"4", "L", "R"})

    def test_threshold_gate_does_not_promote_scientific_PASS(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "spectrum.json"
            p.write_text(json.dumps({"multiplets": [
                {"name": "degenerate", "mass_GeV": 1e16, "beta": {"4": 1.0, "L": 1.0, "R": 1.0}}
            ]}))
            result = th.calculate(p, 1e16, {"4": 31.0, "L": 31.0, "R": 31.0}, {}, 1e-8)
            self.assertEqual(result["gate"], "PASS")
            self.assertEqual(result["scientific_status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
