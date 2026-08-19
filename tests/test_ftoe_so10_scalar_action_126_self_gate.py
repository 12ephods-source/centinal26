import copy
import json
import pathlib
import unittest

from scripts import ftoe_so10_scalar_action_126_self_gate as gate


CONTRACT = pathlib.Path("physics/ftoe/scalar_action_126_self_v12.json")


class ScalarAction126SelfGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_frozen_contract_passes(self) -> None:
        result = gate.evaluate(self.contract)
        self.assertTrue(result["execution_pass"])
        self.assertEqual(
            result["claim_status"], "PARTIAL_ACTION_126_SELF_SECTOR_SOURCE_ENUMERATED"
        )
        self.assertEqual(result["full_action_gate"], "NOT_COMPLETE")

    def test_missing_complex_quartic_fails(self) -> None:
        broken = copy.deepcopy(self.contract)
        broken["self_sector"]["complex_quartic_invariants"] = []
        self.assertFalse(gate.evaluate(broken)["execution_pass"])

    def test_false_full_action_claim_fails(self) -> None:
        broken = copy.deepcopy(self.contract)
        broken["full_action_gate"] = "COMPLETE"
        self.assertFalse(gate.evaluate(broken)["execution_pass"])


if __name__ == "__main__":
    unittest.main()
