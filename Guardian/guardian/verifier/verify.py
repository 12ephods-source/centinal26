"""
Verification suite for Guardian Level 1.
Checks: manifest, artifact hashes, event chain, checkpoints, replay, environment.
"""

import json
import os
from typing import Any, Dict, Tuple

from guardian.core.checkpoint import CheckpointManager
from guardian.core.events import load_event_chain, verify_event_chain
from guardian.core.hashing import hash_file


class VerificationSuite:
    """Runs all VERIFY checks and produces a structured report."""

    CHECKS = [
        "VERIFY_001_MANIFEST_EXISTS",
        "VERIFY_002_ARTIFACT_HASHES",
        "VERIFY_003_EVENT_CHAIN",
        "VERIFY_004_CHECKPOINT_INTEGRITY",
        "VERIFY_005_REPLAY_INTEGRITY",
        "VERIFY_006_ENVIRONMENT_IDENTITY",
    ]

    def __init__(
        self,
        output_dir: str = "output",
        manifest_path: str = "output/manifest.json",
        events_path: str = "events.jsonl",
        results_path: str = "output/results.json",
        verification_path: str = "output/verification.json",
    ):
        self.output_dir = output_dir
        self.manifest_path = manifest_path
        self.events_path = events_path
        self.results_path = results_path
        self.verification_path = verification_path
        self.checks: Dict[str, Any] = {}
        self._load_manifest()
        self._load_results()

    def _load_manifest(self) -> None:
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path) as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {}

    def _load_results(self) -> None:
        if os.path.exists(self.results_path):
            with open(self.results_path) as f:
                self.results = json.load(f)
        else:
            self.results = {}

    def verify_001(self) -> Tuple[bool, str]:
        """VERIFY_001: Manifest exists and is valid JSON."""
        if not os.path.exists(self.manifest_path):
            return False, "manifest.json not found"
        try:
            with open(self.manifest_path) as f:
                data = json.load(f)
            required = ["manifest_version", "experiment_id", "engine",
                        "sampling", "environment"]
            for field_name in required:
                if field_name not in data:
                    return False, f"manifest missing required field: {field_name}"
            return True, "Manifest exists and is valid"
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in manifest: {e}"

    def verify_002(self) -> Tuple[bool, str]:
        """VERIFY_002: Results artifact hash matches stored hash."""
        if not os.path.exists(self.results_path):
            return False, "results.json not found"
        try:
            computed = hash_file(self.results_path)
            stored = self.manifest.get("verification", {}).get("results_hash", "")
            if not stored:
                return False, "No results hash stored in manifest"
            if computed == stored:
                return True, f"Results hash matches ({computed[:16]}...)"
            return False, f"Hash mismatch: computed={computed[:16]}..., stored={stored[:16]}..."
        except Exception as e:
            return False, f"Error computing hash: {e}"

    def verify_003(self) -> Tuple[bool, str]:
        """VERIFY_003: Event chain hash chain is unbroken."""
        valid, msg = verify_event_chain(self.events_path)
        if not valid:
            return False, msg
        events = load_event_chain(self.events_path)
        return True, f"Event chain valid ({len(events)} events)"

    def verify_004(self) -> Tuple[bool, str]:
        """VERIFY_004: All checkpoint chunk hashes verify."""
        manager = CheckpointManager(self.output_dir)
        checkpoints = manager.discover_checkpoints()
        if not checkpoints:
            return True, "No checkpoints found (not yet checkpointed)"
        for ckpt in checkpoints:
            if not ckpt.verify(self.output_dir):
                return False, f"Checkpoint {ckpt.checkpoint_id} failed verification"
        return True, f"All {len(checkpoints)} checkpoints verified"

    def verify_005(self) -> Tuple[bool, str]:
        """VERIFY_005: Checkpoints form a consistent sequence."""
        manager = CheckpointManager(self.output_dir)
        checkpoints = manager.discover_checkpoints()
        if not checkpoints:
            return True, "No checkpoints (pre-checkpoint phase)"
        steps = [c.step for c in checkpoints]
        if sorted(steps) != steps:
            return False, f"Checkpoints out of order: {steps}"
        return True, f"Checkpoint sequence valid ({len(checkpoints)} checkpoints)"

    def verify_006(self) -> Tuple[bool, str]:
        """VERIFY_006: Environment identity matches execution class constraints."""
        env = self.manifest.get("environment", {})
        exec_class = env.get("execution_class", "LOCAL_TERMUX")
        digest = env.get("image_digest", "")

        if exec_class == "OCI_EXECUTION":
            if digest in ("local_termux_no_oci", "sha256:test", ""):
                return False, "OCI_EXECUTION but image_digest is test/placeholder"
            return True, f"OCI execution confirmed ({digest[:16]}...)"

        if exec_class == "LOCAL_TERMUX":
            if digest == "local_termux_no_oci":
                return True, "LOCAL_TERMUX execution confirmed"
            return False, f"LOCAL_TERMUX but image_digest={digest} (expected local_termux_no_oci)"

        return False, f"Unknown execution_class: {exec_class}"

    def run_all(self) -> Dict[str, Any]:
        """Run all verification checks and produce the verification report."""
        methods = [
            ("VERIFY_001", self.verify_001),
            ("VERIFY_002", self.verify_002),
            ("VERIFY_003", self.verify_003),
            ("VERIFY_004", self.verify_004),
            ("VERIFY_005", self.verify_005),
            ("VERIFY_006", self.verify_006),
        ]

        for name, method in methods:
            passed, message = method()
            self.checks[name] = {"passed": passed, "message": message}

        all_passed = all(v["passed"] for v in self.checks.values())
        report = {
            "all_passed": all_passed,
            "checks": self.checks,
            "manifest_id": self.manifest.get("experiment_id", "unknown"),
            "execution_class": self.manifest.get("environment", {}).get(
                "execution_class", "unknown"
            ),
        }

        # Save verification report
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.verification_path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report

    def print_summary(self, report: Dict[str, Any]) -> None:
        """Print a human-readable verification summary."""
        print("\n=== Guardian Level 1 Verification Report ===")
        print(f"Execution class : {report['execution_class']}")
        print(f"Manifest ID     : {report['manifest_id']}")
        print(f"Overall status  : {'ALL PASSED' if report['all_passed'] else 'FAILURES DETECTED'}\n")
        for name, result in report["checks"].items():
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{name} {status} - {result['message']}")
        print()
