import importlib.util
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "ftoe_so10_group_theory_gate.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_group_theory_gate", PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class G422GroupTheoryGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = mod.calculate()
        cls.registry = mod.load_registry()
        cls.fields = cls.registry["fields"]

    def test_scalar_dynkin_totals(self):
        self.assertEqual(mod.scalar_dynkin_totals(self.fields), (Fraction(25), Fraction(16), Fraction(38)))

    def test_fermion_kappa_dynkin_totals(self):
        self.assertEqual(mod.fermion_dynkin_totals(self.fields), (Fraction(3), Fraction(3), Fraction(3)))

    def test_one_loop_is_derived_exactly(self):
        self.assertEqual(mod.one_loop(self.fields), (Fraction(-7, 3), Fraction(2), Fraction(28, 3)))

    def test_two_loop_is_derived_exactly(self):
        expected = (
            (Fraction(2435, 6), Fraction(105, 2), Fraction(249, 2)),
            (Fraction(525, 2), Fraction(73), Fraction(48)),
            (Fraction(1245, 2), Fraction(48), Fraction(835, 3)),
        )
        self.assertEqual(mod.two_loop(self.fields), expected)

    def test_disputed_entry_is_independently_525_over_2(self):
        self.assertEqual(mod.two_loop(self.fields)[1][0], Fraction(525, 2))
        self.assertNotEqual(mod.two_loop(self.fields)[1][0], Fraction(525, 3))

    def test_gate_passes(self):
        self.assertEqual(self.result["overall"], "PASS")


if __name__ == "__main__":
    unittest.main()
