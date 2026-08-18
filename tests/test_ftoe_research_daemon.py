import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


legacy = load_module("ftoe_research_daemon", ROOT / "scripts/ftoe_research_daemon.py")
supervisor = load_module("ftoe_secure_supervisor_for_tests", ROOT / "scripts/ftoe_secure_supervisor.py")


class ResearchDaemonTests(unittest.TestCase):
    def test_legacy_direct_provider_daemon_fails_closed(self):
        self.assertEqual(legacy.main(), 2)
        self.assertIn("Deprecated", legacy.MESSAGE)

    def test_publication_gate_fails_closed(self):
        self.assertFalse(supervisor.publication_ready([{"returncode": 0}]))

    def test_allowlist_contains_no_shell(self):
        forbidden = {"bash", "sh", "zsh", "fish", "sudo", "su"}
        for command in supervisor.ALLOWLIST:
            self.assertNotIn(pathlib.Path(command[0]).name, forbidden)

    def test_priority_scheduler_selects_first_nonpass(self):
        pub = {
            "mandatory": {
                "radiative_naturalness": "PASS",
                "frozen_uv_action": "REVIEW",
                "vacuum_and_mass_spectrum": "REVIEW",
            }
        }
        self.assertEqual(supervisor.next_gate(pub), ("frozen_uv_action", "REVIEW"))

    def test_fail_vote_is_never_averaged_away(self):
        panel = [
            {"status": "OK", "response": {"status": "PASS", "evidence_refs": ["a"]}},
            {"status": "OK", "response": {"status": "FAIL", "evidence_refs": ["b"]}},
            {"status": "OK", "response": {"status": "PASS", "evidence_refs": ["c"]}},
        ]
        result = supervisor.arbitration(panel)
        self.assertTrue(result["disagreement"])
        self.assertEqual(result["conservative_status"], "FAIL")

    def test_review_blocks_consensus_pass(self):
        panel = [
            {"status": "OK", "response": {"status": "PASS", "evidence_refs": ["a"]}},
            {"status": "OK", "response": {"status": "REVIEW", "evidence_refs": ["b"]}},
        ]
        self.assertEqual(supervisor.arbitration(panel)["conservative_status"], "REVIEW")

    def test_single_pass_does_not_count_as_independent_pass(self):
        panel = [{"status": "OK", "response": {"status": "PASS", "evidence_refs": ["a"]}}]
        self.assertEqual(supervisor.arbitration(panel)["conservative_status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
