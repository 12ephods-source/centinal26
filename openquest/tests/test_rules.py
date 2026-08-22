import unittest

from openquest.rules import get_profile, level_one_hit_points
from openquest.validator import Character, GateStatus, validate_character


class RuleDataTests(unittest.TestCase):
    def make_character(self, **overrides):
        base = {
            "name": "Rule Data Hero",
            "ability_scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            "class_name": "Fighter",
            "species": "Human",
            "background": "Soldier",
            "proficiencies": ["light armor", "medium armor", "shields"],
            "skill_proficiencies": ["athletics", "perception"],
            "hit_points": 11,
            "armor_class": 16,
        }
        base.update(overrides)
        return Character(**base)

    def test_profiles_are_versioned(self):
        self.assertEqual(get_profile("srd-5.2.1").source_id, "srd-5.2.1")
        self.assertEqual(get_profile("srd-5.1").source_id, "srd-5.1")

    def test_fighter_level_one_hp_is_derived(self):
        fighter = get_profile("srd-5.2.1").classes["Fighter"]
        self.assertEqual(level_one_hit_points(fighter, 13), 11)

    def test_wrong_fighter_hp_fails(self):
        results = validate_character(self.make_character(hit_points=12))
        self.assertTrue(any(r.gate == "RULE_DATA_GATE" and r.status == GateStatus.FAIL for r in results))

    def test_wrong_skill_count_fails(self):
        results = validate_character(self.make_character(skill_proficiencies=["athletics"]))
        self.assertTrue(any(r.gate == "RULE_DATA_GATE" and r.status == GateStatus.FAIL for r in results))

    def test_invalid_fighter_skill_fails(self):
        results = validate_character(
            self.make_character(skill_proficiencies=["athletics", "sleight of hand"])
        )
        self.assertTrue(any(r.gate == "RULE_DATA_GATE" and r.status == GateStatus.FAIL for r in results))

    def test_unknown_class_fails_closed(self):
        results = validate_character(self.make_character(class_name="Wizard"))
        self.assertTrue(any(r.gate == "RULE_DATA_GATE" and r.status == GateStatus.FAIL for r in results))

    def test_legacy_profile_is_explicit(self):
        character = self.make_character(import_format="2014")
        results = validate_character(character)
        self.assertEqual(character.ruleset, "srd-5.1")
        self.assertTrue(all(r.status == GateStatus.PASS for r in results), results)


if __name__ == "__main__":
    unittest.main()
