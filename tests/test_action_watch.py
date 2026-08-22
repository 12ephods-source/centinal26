import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "deploy" / "termux" / "library_cleaner" / "action_watch.py"
spec = importlib.util.spec_from_file_location("action_watch", MODULE)
action_watch = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(action_watch)


class ActionWatchTests(unittest.TestCase):
    def test_new_ci_failure_is_actionable(self):
        old = {"github": {"workflow_runs": {"CI:main": {"conclusion": "success"}}, "pull_requests": {}}, "gates": {}}
        new = {"github": {"workflow_runs": {"CI:main": {"conclusion": "failure", "html_url": "x"}}, "pull_requests": {}}, "gates": {}}
        changes = action_watch.actionable_changes(old, new)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["kind"], "CI")

    def test_repeated_ci_failure_is_noise(self):
        run = {"conclusion": "failure", "html_url": "x"}
        old = {"github": {"workflow_runs": {"CI:main": run}, "pull_requests": {}}, "gates": {}}
        new = {"github": {"workflow_runs": {"CI:main": run}, "pull_requests": {}}, "gates": {}}
        self.assertEqual(action_watch.actionable_changes(old, new), [])

    def test_head_commit_change_alone_is_noise(self):
        old = {"github": {"workflow_runs": {}, "pull_requests": {"7": {"title": "x", "draft": False, "head_sha": "a"}}}, "gates": {}}
        new = {"github": {"workflow_runs": {}, "pull_requests": {"7": {"title": "x", "draft": False, "head_sha": "b"}}}, "gates": {}}
        self.assertEqual(action_watch.actionable_changes(old, new), [])

    def test_ready_for_review_transition_is_actionable(self):
        old = {"github": {"workflow_runs": {}, "pull_requests": {"7": {"title": "x", "draft": True, "head_sha": "a"}}}, "gates": {}}
        new = {"github": {"workflow_runs": {}, "pull_requests": {"7": {"title": "x", "draft": False, "head_sha": "a"}}}, "gates": {}}
        changes = action_watch.actionable_changes(old, new)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["kind"], "PR")

    def test_pending_physical_gate_change_is_actionable(self):
        old = {"github": {"workflow_runs": {}, "pull_requests": {}}, "gates": {"physical_device": {"status": "VERIFIED_COMPLETE"}}}
        new = {"github": {"workflow_runs": {}, "pull_requests": {}}, "gates": {"physical_device": {"status": "BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE"}}}
        changes = action_watch.actionable_changes(old, new)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["kind"], "GATE")
        self.assertEqual(changes[0]["affected_item"], "physical_device")

    def test_verified_gate_change_is_not_action_noise(self):
        old = {"github": {"workflow_runs": {}, "pull_requests": {}}, "gates": {"release_engineering": {"status": "PENDING"}}}
        new = {"github": {"workflow_runs": {}, "pull_requests": {}}, "gates": {"release_engineering": {"status": "VERIFIED_COMPLETE_HOST"}}}
        self.assertEqual(action_watch.actionable_changes(old, new), [])

    def test_atomic_write_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            action_watch.atomic_write(path, {"a": 1})
            self.assertEqual(action_watch.load_json(path, {}), {"a": 1})


if __name__ == "__main__":
    unittest.main()
