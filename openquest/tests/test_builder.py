import unittest

from openquest.builder import build_level_one_character, list_options
from openquest.validator import GateStatus


class CharacterBuilderTests(unittest.TestCase):
    def abilities(self):
        return {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}

    def test_options_are_generated_from_selected_profile(self):
        options = list_options("srd-5.2.1")
        self.assertEqual(options.classes, ("Fighter",))
        self.assertEqual(options.species, ("Human",))
        self.assertEqual(options.backgrounds, ("Soldier",))
        self.assertEqual(options.standard_array, (15, 14, 13, 12, 10, 8))

    def test_builder_derives_rules_data_and_returns_valid_character(self):
        result = build_level_one_character(
            name="Builder Hero",
            ability_scores=self.abilities(),
            class_name="Fighter",
            species="Human",
            background="Soldier",
            skill_proficiencies=["athletics", "perception"],
        )
        self.assertTrue(result.valid, result.gates)
        self.assertIsNotNone(result.character)
        self.assertEqual(result.character.hit_points, 11)
        self.assertIn("martial weapons", result.character.proficiencies)
        self.assertTrue(all(g.status == GateStatus.PASS for g in result.gates))

    def test_builder_rejects_non_standard_array(self):
        abilities = self.abilities()
        abilities["str"] = 16
        result = build_level_one_character(
            name="Illegal Hero",
            ability_scores=abilities,
            class_name="Fighter",
            species="Human",
            background="Soldier",
            skill_proficiencies=["athletics", "perception"],
        )
        self.assertFalse(result.valid)
        self.assertIsNone(result.character)
        self.assertTrue(any(g.gate == "BUILD_GATE" for g in result.gates))

    def test_builder_rejects_illegal_skill_before_character_creation(self):
        result = build_level_one_character(
            name="Illegal Skill Hero",
            ability_scores=self.abilities(),
            class_name="Fighter",
            species="Human",
            background="Soldier",
            skill_proficiencies=["athletics", "sleight of hand"],
        )
        self.assertFalse(result.valid)
        self.assertIsNone(result.character)

    def test_builder_can_construct_legacy_profile_explicitly(self):
        result = build_level_one_character(
            name="Legacy Hero",
            ability_scores=self.abilities(),
            class_name="Fighter",
            species="Human",
            background="Soldier",
            skill_proficiencies=["athletics", "perception"],
            ruleset="srd-5.1",
        )
        self.assertTrue(result.valid, result.gates)
        self.assertEqual(result.character.ruleset, "srd-5.1")


if __name__ == "__main__":
    unittest.main()
