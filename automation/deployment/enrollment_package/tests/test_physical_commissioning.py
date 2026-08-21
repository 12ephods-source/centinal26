from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from automation.deployment.enrollment_package.verify_physical_commissioning import (
    verify_commissioning,
)
from automation.device.verify_worker_heartbeat import canonical_record_sha256

SOURCE_COMMIT = "a" * 40
DEVICE_ID = "test-android-device"
BOOT_ID = "11111111-2222-3333-4444-555555555555"


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _build_package(root: Path) -> None:
    evidence = {
        "schema_version": "1.0",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "device_id": DEVICE_ID,
        "status": "DEVICE_EVIDENCE_CAPTURED",
        "physical_device_gate": "EVIDENCE_CAPTURED_UNVERIFIED",
        "software_provenance": {"source_commit": SOURCE_COMMIT},
        "platform": {
            "boot_id": BOOT_ID,
            "android_detection": {
                "is_android": True,
                "signals": {
                    "ANDROID_ROOT": None,
                    "ANDROID_DATA": None,
                    "system_build_prop": False,
                    "termux_prefix": True,
                },
            },
        },
        "package_inventory_sources": ["android_packages_pm"],
    }
    report = {
        "device_id": DEVICE_ID,
        "status": "DEVICE_EVIDENCE_CAPTURED",
        "physical_device_gate": "EVIDENCE_CAPTURED_UNVERIFIED",
        "source_commit": SOURCE_COMMIT,
    }
    _write_json(root / "device_evidence.json", evidence)
    _write_json(root / "validation_report.json", report)
    manifest = {
        "schema_version": "1.0",
        "files": {
            "device_evidence.json": hashlib.sha256(
                (root / "device_evidence.json").read_bytes()
            ).hexdigest(),
            "validation_report.json": hashlib.sha256(
                (root / "validation_report.json").read_bytes()
            ).hexdigest(),
        },
    }
    _write_json(root / "MANIFEST.sha256.json", manifest)
    enrollment_digest = hashlib.sha256(
        (root / "MANIFEST.sha256.json").read_bytes()
    ).hexdigest()
    heartbeat = {
        "schema_version": "1.0",
        "device_id": DEVICE_ID,
        "sequence": 1,
        "timestamp": datetime.now(UTC).isoformat(),
        "boot_id": BOOT_ID,
        "platform": {
            "system": "Linux",
            "release": "android",
            "machine": "aarch64",
            "android_termux_signal": True,
        },
        "enrollment_digest": enrollment_digest,
        "status": "ONLINE_OBSERVED",
        "verification_status": "PENDING_CONTROLLER_VERIFICATION",
    }
    heartbeat["record_sha256"] = canonical_record_sha256(heartbeat)
    _write_json(root / "worker_heartbeat.json", heartbeat)


def test_one_shot_commissioning_verifies_enrollment_and_heartbeat(tmp_path: Path) -> None:
    _build_package(tmp_path)
    result = verify_commissioning(tmp_path, SOURCE_COMMIT)
    assert result["status"] == "VERIFIED_PHYSICAL_COMMISSIONING_ELIGIBLE"
    assert result["enrollment"]["integrity"] == "VERIFIED"
    assert result["heartbeat"]["eligible"] is True
    assert result["worker_activation"] == "VERIFIED_ACTIVE_ELIGIBLE"


def test_heartbeat_bound_to_wrong_enrollment_digest_fails(tmp_path: Path) -> None:
    _build_package(tmp_path)
    path = tmp_path / "worker_heartbeat.json"
    heartbeat = json.loads(path.read_text(encoding="utf-8"))
    heartbeat["enrollment_digest"] = "0" * 64
    heartbeat["record_sha256"] = canonical_record_sha256(heartbeat)
    _write_json(path, heartbeat)
    result = verify_commissioning(tmp_path, SOURCE_COMMIT)
    assert result["status"] == "REJECTED"
    assert "ENROLLMENT_DIGEST_MISMATCH" in result["errors"]
