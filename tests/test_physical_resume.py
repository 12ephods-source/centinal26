import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "deploy" / "termux" / "library_cleaner" / "physical_resume.py"
spec = importlib.util.spec_from_file_location("physical_resume", MODULE)
physical_resume = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(physical_resume)


class PhysicalResumeTests(unittest.TestCase):
    def test_termux_detection_requires_android_and_termux_prefix(self):
        self.assertTrue(
            physical_resume.is_android_termux(
                {
                    "PREFIX": "/data/data/com.termux/files/usr",
                    "ANDROID_ROOT": "/system",
                }
            )
        )
        self.assertFalse(
            physical_resume.is_android_termux(
                {"PREFIX": "/usr", "ANDROID_ROOT": "/system"}
            )
        )
        self.assertFalse(
            physical_resume.is_android_termux(
                {"PREFIX": "/data/data/com.termux/files/usr"}
            )
        )

    def test_physical_source_is_taken_only_from_canonical_gate(self):
        state = {
            "physical_gate": {
                "status": "BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE",
                "qualified_source_commit": "abc123",
            }
        }
        self.assertEqual(
            physical_resume.physical_source(state),
            ("BLOCKED_EXTERNAL_PHYSICAL_EVIDENCE", "abc123"),
        )

    def test_non_termux_runtime_does_not_execute_device_path(self):
        original = physical_resume.is_android_termux
        try:
            physical_resume.is_android_termux = lambda env=None: False
            result = physical_resume.resume()
        finally:
            physical_resume.is_android_termux = original
        self.assertEqual(result["status"], "NOT_APPLICABLE_NON_TERMUX")
        self.assertFalse(result["executed"])


if __name__ == "__main__":
    unittest.main()
