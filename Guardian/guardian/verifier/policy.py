"""
Attestation policy: decides whether to sign or defer based on verification results.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from guardian.core.events import log_event


class AttestationPolicy:
    """
    Policy for signing or deferring attestation.
    Signs only if all VERIFY checks pass and the execution class is valid.
    """

    REQUIRED_CHECKS = [
        "VERIFY_001",
        "VERIFY_002",
        "VERIFY_003",
        "VERIFY_004",
        "VERIFY_005",
        "VERIFY_006",
    ]

    def __init__(
        self,
        verification_report: Dict[str, Any],
        manifest: Dict[str, Any],
        events_path: str = "events.jsonl",
        attestation_path: str = "output/attestation.json",
    ):
        self.report = verification_report
        self.manifest = manifest
        self.events_path = events_path
        self.attestation_path = attestation_path

    def evaluate(self) -> Tuple[bool, str]:
        """
        Evaluate whether attestation should be signed or deferred.
        Returns (attestation_signed, reason).
        """
        if not self.report.get("all_passed"):
            return False, "VERIFICATION_FAILED: not all checks passed"

        exec_class = self.report.get("execution_class", "")
        if exec_class not in ("LOCAL_TERMUX", "OCI_EXECUTION"):
            return False, f"INVALID_EXECUTION_CLASS: {exec_class}"

        if exec_class == "OCI_EXECUTION":
            digest = self.manifest.get("environment", {}).get("image_digest", "")
            if not digest or digest in ("local_termux_no_oci", "sha256:test"):
                return False, "OCI_EXECUTION but image_digest not set to a real OCI digest"

        return True, f"ATTESTATION_APPROVED ({exec_class})"

    def sign(self) -> Dict[str, Any]:
        """Create and persist the attestation record."""
        approved, reason = self.evaluate()
        attestation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "approved": approved,
            "reason": reason,
            "verification_summary": {
                k: v["passed"] for k, v in self.report.get("checks", {}).items()
            },
            "manifest_hash": self.manifest.get("experiment_id", ""),
            "execution_class": self.report.get("execution_class", ""),
        }

        os.makedirs(os.path.dirname(self.attestation_path) or ".", exist_ok=True)
        with open(self.attestation_path, "w") as f:
            json.dump(attestation, f, indent=2, ensure_ascii=False)

        return attestation


def determine_attestation(
    verification_report: Dict[str, Any],
    manifest: Dict[str, Any],
    events_path: str = "events.jsonl",
    attestation_path: str = "output/attestation.json",
) -> Dict[str, Any]:
    """One-step attestation decision and signing."""
    policy = AttestationPolicy(
        verification_report=verification_report,
        manifest=manifest,
        events_path=events_path,
        attestation_path=attestation_path,
    )
    approved, reason = policy.evaluate()
    attestation = policy.sign()

    log_event(
        "ATTESTATION_SIGNED" if approved else "ATTESTATION_DEFERRED",
        {
            "approved": approved,
            "reason": reason,
            "attestation_path": attestation_path,
        },
        events_path,
    )

    return attestation
