import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ftoe_so10_exact_shift_no_go", ROOT / "scripts/ftoe_so10_exact_shift_no_go.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class ExactShiftNoGoTests(unittest.TestCase):
    def test_frozen_charged_doublet_has_no_nontrivial_exact_shift(self):
        result = mod.calculate(0.5, True)
        self.assertFalse(result.nontrivial_constant_shift_exists)
        self.assertEqual(result.exact_additive_shift_status, "FAIL")
        self.assertEqual(result.nonlinear_collective_or_sequestered_status, "REVIEW")

    def test_zero_gauge_coupling_removes_this_specific_obstruction(self):
        self.assertTrue(mod.nontrivial_constant_shift_exists(0.5, False))

    def test_neutral_field_not_excluded_by_hypercharge_argument_alone(self):
        self.assertTrue(mod.nontrivial_constant_shift_exists(0.0, True))


if __name__ == "__main__":
    unittest.main()
