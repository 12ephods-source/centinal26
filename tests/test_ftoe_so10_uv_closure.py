import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


op = load(
    "ftoe_so10_operator_gate_test",
    ROOT / "scripts" / "ftoe_so10_operator_gate.py",
)
th = load(
    "ftoe_so10_threshold_gate_test",
    ROOT / "scripts" / "ftoe_so10_threshold_gate.py",
)
nat = load(
    "ftoe_so10_naturalness_gate_test",
    ROOT / "scripts" / "ftoe_so10_naturalness_gate.py",
)
rad = load(
    "ftoe_so10_radiative_protection_gate_test",
    ROOT / "scripts" / "ftoe_so10_radiative_protection_gate.py",
)


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

    def test_z11_selector_delays_b3_sk_tower_to_dimension_13(self):
        self.assertEqual(op.first_allowed_spurion_power(11, 1, 1), 10)
        rows = op.selector_search(13, n_max=11)
        self.assertTrue(
            any(
                row["N"] == 11 and row["q_B3"] == 1 and row["q_S"] == 1
                for row in rows
            )
        )

    def test_current_two_loop_mu_prefers_order_one_n9(self):
        result = op.calculate(2.04990990688745e16)
        self.assertEqual(result.preferred_power, 9)
        self.assertEqual(result.preferred_operator_dimension, 13)
        self.assertTrue(0.1 < result.preferred_coefficient_times_Ceff < 10.0)
        self.assertEqual(result.scientific_status, "REVIEW")
        self.assertEqual(result.gates["actual_Clebsch_factor_Ceff"], "NOT_TESTED")


class NaturalnessGateTests(unittest.TestCase):
    def test_generic_portal_requires_extreme_suppression(self):
        result = nat.calculate(
            2.04990990688745e16,
            9.54e3,
            0.032067325570772874,
        )
        self.assertLess(result.required_portal_max, 3e-25)
        self.assertGreater(result.required_portal_max, 1e-25)
        self.assertGreater(result.tuning_inverse, 1e24)
        self.assertEqual(result.simple_embedded_doublet_status, "FAIL")
        self.assertEqual(
            result.protected_pNGB_or_sequestered_branch_status,
            "REVIEW",
        )

    def test_gauge_loop_proxy_is_far_above_required_portal(self):
        result = nat.calculate(
            2.04990990688745e16,
            9.54e3,
            0.032067325570772874,
        )
        self.assertGreater(result.gauge_loop_proxy, 1e-4)
        self.assertGreater(result.loop_proxy_over_required_portal, 1e20)
        self.assertEqual(
            result.gates["radiative_stability_of_protection"],
            "NOT_TESTED",
        )


class RadiativeProtectionGateTests(unittest.TestCase):
    def test_single_spurion_gut_scale_pngb_fails_by_many_orders(self):
        result = rad.calculate(
            2.04990990688745e16,
            9.54e3,
            0.032067325570772874,
        )
        self.assertEqual(result.single_spurion_GUT_scale_pNGB_status, "FAIL")
        self.assertGreater(result.one_loop_gauge_spurion, 1e-4)
        self.assertLess(result.target_mass_squared_ratio, 3e-25)
        self.assertGreater(result.reference_one_loop_mass_over_mu_I, 1e9)
        self.assertGreaterEqual(result.minimum_equal_spurion_loop_order, 9)
        self.assertEqual(result.collective_or_sequestered_branch_status, "REVIEW")

    def test_loop_order_is_monotonic_and_fail_closed(self):
        target = 2e-25
        weak = rad.minimum_loop_order(1e-2, target)
        strong = rad.minimum_loop_order(1e-3, target)
        self.assertGreaterEqual(weak, strong)
        self.assertGreater(strong, 1)


class ThresholdGateTests(unittest.TestCase):
    def test_zero_log_thresholds_leave_couplings_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spectrum.json"
            path.write_text(
                json.dumps(
                    {
                        "multiplets": [
                            {
                                "name": "A",
                                "mass_GeV": 1e16,
                                "beta": {"4": 1.0, "L": 2.0, "R": 3.0},
                            }
                        ]
                    }
                )
            )
            spectrum = th.load_spectrum(path)
            delta = th.threshold_corrections(spectrum, 1e16)
            for value in delta.values():
                self.assertAlmostEqual(value, 0.0, places=15)

    def test_synthetic_frozen_spectrum_correction_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spectrum.json"
            path.write_text(
                json.dumps(
                    {
                        "multiplets": [
                            {
                                "name": "A",
                                "mass_GeV": 2e16,
                                "beta": {"4": 1.0, "L": 0.0, "R": -1.0},
                            },
                            {
                                "name": "B",
                                "mass_GeV": 0.5e16,
                                "beta": {"4": -0.5, "L": 1.0, "R": 0.0},
                            },
                        ]
                    }
                )
            )
            first = th.threshold_corrections(th.load_spectrum(path), 1e16)
            second = th.threshold_corrections(th.load_spectrum(path), 1e16)
            self.assertEqual(first, second)
            self.assertEqual(set(first), {"4", "L", "R"})

    def test_threshold_gate_does_not_promote_scientific_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spectrum.json"
            path.write_text(
                json.dumps(
                    {
                        "multiplets": [
                            {
                                "name": "degenerate",
                                "mass_GeV": 1e16,
                                "beta": {"4": 1.0, "L": 1.0, "R": 1.0},
                            }
                        ]
                    }
                )
            )
            result = th.calculate(
                path,
                1e16,
                {"4": 31.0, "L": 31.0, "R": 31.0},
                {},
                1e-8,
            )
            self.assertEqual(result["gate"], "PASS")
            self.assertEqual(result["scientific_status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
