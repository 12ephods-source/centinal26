import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openquest.cli import main


class CliTests(unittest.TestCase):
    abilities = '{"str":15,"dex":14,"con":13,"int":12,"wis":10,"cha":8}'

    def run_cli(self, argv):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(argv)
        return code, stream.getvalue()

    def test_options_contract(self):
        code, output = self.run_cli(["options"])
        payload = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(payload["ruleset"], "srd-5.2.1")
        self.assertEqual(payload["classes"], ["Fighter"])

    def test_create_validate_export_contract(self):
        code, output = self.run_cli(
            [
                "create",
                "--name",
                "CLI Hero",
                "--class",
                "Fighter",
                "--species",
                "Human",
                "--background",
                "Soldier",
                "--skill",
                "athletics",
                "--skill",
                "perception",
                "--abilities",
                self.abilities,
            ]
        )
        payload = json.loads(output)
        self.assertEqual(code, 0)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["character"]["name"], "CLI Hero")
        self.assertEqual(payload["character"]["hit_points"], 11)

    def test_invalid_build_is_machine_readable_failure(self):
        code, output = self.run_cli(
            [
                "create",
                "--name",
                "Bad Hero",
                "--class",
                "Fighter",
                "--species",
                "Human",
                "--background",
                "Soldier",
                "--skill",
                "sleight of hand",
                "--skill",
                "perception",
                "--abilities",
                self.abilities,
            ]
        )
        payload = json.loads(output)
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "FAIL")
        self.assertTrue(any(gate["gate"] == "BUILD_GATE" for gate in payload["gates"]))

    def test_output_file_matches_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "character.json"
            code, output = self.run_cli(
                [
                    "create",
                    "--name",
                    "File Hero",
                    "--class",
                    "Fighter",
                    "--species",
                    "Human",
                    "--background",
                    "Soldier",
                    "--skill",
                    "athletics",
                    "--skill",
                    "perception",
                    "--abilities",
                    self.abilities,
                    "--output",
                    str(path),
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(path.read_text()), json.loads(output))


if __name__ == "__main__":
    unittest.main()
