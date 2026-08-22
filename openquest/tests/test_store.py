import tempfile
import unittest
from pathlib import Path

from openquest.builder import build_level_one_character
from openquest.store import list_characters, load_character, save_character
from openquest.validator import export_character


class CharacterStoreTests(unittest.TestCase):
    def payload(self):
        result = build_level_one_character(
            name="Stored Hero",
            ability_scores={"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            class_name="Fighter",
            species="Human",
            background="Soldier",
            skill_proficiencies=["athletics", "perception"],
        )
        self.assertTrue(result.valid)
        return __import__("json").loads(export_character(result.character, list(result.gates)))

    def test_save_load_and_list_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = save_character(self.payload(), root)
            loaded = load_character(record["id"], root)
            self.assertEqual(loaded, record)
            listing = list_characters(root)
            self.assertEqual(len(listing), 1)
            self.assertEqual(listing[0]["name"], "Stored Hero")
            self.assertEqual(listing[0]["ruleset"], "srd-5.2.1")

    def test_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = save_character(self.payload(), root)
            path = root / f"{record['id']}.json"
            path.write_text(path.read_text().replace("Stored Hero", "Tampered Hero"))
            with self.assertRaises(ValueError):
                load_character(record["id"], root)


if __name__ == "__main__":
    unittest.main()
