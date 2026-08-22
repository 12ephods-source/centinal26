import json
import unittest

from openquest.validator import Character, GateStatus, export_character, resolve_ruleset, validate_character


class ValidatorTests(unittest.TestCase):
    def make_character(self, **overrides):
        base = dict(
            name="Test Hero",
            ability_scores={"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            class_name="Fighter",
            species="Human",
            background="Soldier",
            proficiencies=["light armor", "medium armor", "shields"],
            skill_proficiencies=["athletics", "perception"],
            hit_points=11,
            armor_class=16,
        )
        base.update(overrides)
        return Character(**base)

    def test_new_character_defaults_to_521(self):
        c = self.make_character()
        result = resolve_ruleset(c)
        self.assertEqual(result.status, GateStatus.PASS)
        self.assertEqual(c.ruleset, "srd-5.2.1")

    def test_2014_import_uses_51(self):
        c = self.make_character(import_format="2014")
        result = resolve_ruleset(c)
        self.assertEqual(result.status, GateStatus.PASS)
        self.assertEqual(c.ruleset, "srd-5.1")

    def test_ambiguous_import_is_unresolved(self):
        c = self.make_character(import_format="unknown-format")
        result = resolve_ruleset(c)
        self.assertEqual(result.status, GateStatus.UNRESOLVED)

    def test_campaign_override_wins(self):
        c = self.make_character(ruleset="srd-5.2.1")
        result = resolve_ruleset(c, "srd-5.1")
        self.assertEqual(result.status, GateStatus.PASS)
        self.assertEqual(c.ruleset, "srd-5.1")

    def test_complete_level_one_character_passes(self):
        c = self.make_character()
        results = validate_character(c)
        self.assertTrue(all(r.status == GateStatus.PASS for r in results), results)

    def test_duplicate_proficiency_fails(self):
        c = self.make_character(skill_proficiencies=["athletics", "athletics"])
        results = validate_character(c)
        failures = [r for r in results if r.status == GateStatus.FAIL]
        self.assertTrue(any(r.gate == "VALIDATION_GATE" for r in failures))

    def test_missing_required_field_fails(self):
        c = self.make_character(background=None)
        results = validate_character(c)
        self.assertTrue(any(r.gate == "CHARACTER_GATE" and r.status == GateStatus.FAIL for r in results))

    def test_export_contains_provenance_and_gate_state(self):
        c = self.make_character()
        results = validate_character(c)
        data = json.loads(export_character(c, results))
        self.assertEqual(data["ruleset"], "srd-5.2.1")
        self.assertEqual(data["source"]["license_id"], "CC-BY-4.0")
        self.assertTrue(data["valid"])


if __name__ == "__main__":
    unittest.main()
