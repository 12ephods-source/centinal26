import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "ftoe_so10_collective_admission_gate.py"
spec = importlib.util.spec_from_file_location("ftoe_so10_collective_admission_gate", PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class CollectiveAdmissionGateTests(unittest.TestCase):
    def test_current_frozen_contract_fails_admission(self):
        result = mod.evaluate(mod.load_contract())
        self.assertEqual(
            result["collective_protection_admission"],
            "FAIL_CURRENT_FROZEN_BRANCH",
        )
        self.assertEqual(result["gates"]["protected_sector_constructed"], "FAIL")
        self.assertEqual(
            result["gates"]["renormalizable_portal_suppression_proved"],
            "FAIL",
        )
        self.assertEqual(result["gates"]["radiative_stability_proved"], "FAIL")

    def test_synthetic_collective_contract_can_pass_structural_admission(self):
        contract = json.loads(json.dumps(mod.load_contract()))
        protected = contract["required_so10_representations"]["protected_I_sector"]
        protected.update(
            {
                "status": "FROZEN",
                "mechanism": "synthetic-test-collective-pNGB",
                "symmetry_structure": "G/H synthetic test coset",
                "collective_breaking_couplings": ["g1", "g2"],
                "portal_suppression_proof": "synthetic proof marker",
                "radiative_stability_proof": "synthetic proof marker",
            }
        )
        contract["scalar_potential_provenance"]["protected_I_extension"] = (
            "CLOSED_FOR_SYNTHETIC_TEST"
        )
        result = mod.evaluate(contract)
        self.assertEqual(result["collective_protection_admission"], "PASS")

    def test_single_collective_coupling_is_insufficient(self):
        contract = json.loads(json.dumps(mod.load_contract()))
        protected = contract["required_so10_representations"]["protected_I_sector"]
        protected.update(
            {
                "status": "FROZEN",
                "mechanism": "synthetic-test-collective-pNGB",
                "symmetry_structure": "G/H synthetic test coset",
                "collective_breaking_couplings": ["g1"],
                "portal_suppression_proof": "synthetic proof marker",
                "radiative_stability_proof": "synthetic proof marker",
            }
        )
        contract["scalar_potential_provenance"]["protected_I_extension"] = (
            "CLOSED_FOR_SYNTHETIC_TEST"
        )
        result = mod.evaluate(contract)
        self.assertEqual(
            result["gates"]["collective_or_sequestered_structure_frozen"],
            "FAIL",
        )


if __name__ == "__main__":
    unittest.main()
