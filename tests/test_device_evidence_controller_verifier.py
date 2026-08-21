from importlib import util
from pathlib import Path

CAPTURE_PATH = Path(__file__).resolve().parents[1] / "automation" / "deployment" / "enrollment_package" / "capture_device_evidence.py"
VERIFY_PATH = Path(__file__).resolve().parents[1] / "automation" / "deployment" / "enrollment_package" / "verify_device_evidence.py"
SOURCE_COMMIT = "a" * 40


def load(path: Path, name: str):
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def android_evidence():
    return {
        "schema_version": "1.2",
        "captured_at_utc": "2026-08-21T00:00:00+00:00",
        "device_id": "phone-1",
        "status": "DEVICE_EVIDENCE_CAPTURED",
        "physical_device_gate": "EVIDENCE_CAPTURED_UNVERIFIED",
        "software_provenance": {
            "repository": "12ephods-source/centinal26",
            "source_commit": SOURCE_COMMIT,
            "status": "OBSERVED",
        },
        "platform": {
            "boot_id": "12345678-1234-1234-1234-123456789abc",
            "android_detection": {
                "is_android": True,
                "signals": {
                    "ANDROID_ROOT": "/system",
                    "ANDROID_DATA": "/data",
                    "system_build_prop": True,
                    "termux_prefix": True,
                },
            },
        },
        "device_profile": {
            "manufacturer": "samsung",
            "model": "SM-A155M",
            "android_version": "16",
            "android_sdk": "36",
            "cpu_architecture": "aarch64",
            "termux_version": "googleplay.2026.06.21",
            "termux_tools_version": "3.0.9",
        },
        "package_inventory_sources": ["android_packages_pm"],
        "commands": {},
        "claims": {},
    }


def test_valid_bundle_becomes_enrollment_eligible(tmp_path):
    capture = load(CAPTURE_PATH, "capture_device_evidence")
    verifier = load(VERIFY_PATH, "verify_device_evidence")
    capture.write_bundle(tmp_path, android_evidence())
    result = verifier.verify_bundle(tmp_path, expected_source_commit=SOURCE_COMMIT)
    assert result["integrity"] == "VERIFIED"
    assert result["software_provenance"] == "VERIFIED_EXPECTED_COMMIT"
    assert result["device_profile"]["model"] == "SM-A155M"
    assert result["enrollment"] == "VERIFIED_ELIGIBLE"
    assert result["worker_activation"] == "ELIGIBLE_PENDING_HEARTBEAT"


def test_tampered_bundle_is_rejected(tmp_path):
    capture = load(CAPTURE_PATH, "capture_device_evidence_tamper")
    verifier = load(VERIFY_PATH, "verify_device_evidence_tamper")
    capture.write_bundle(tmp_path, android_evidence())
    evidence = tmp_path / "device_evidence.json"
    evidence.write_text(evidence.read_text() + "\n", encoding="utf-8")
    result = verifier.verify_bundle(tmp_path, expected_source_commit=SOURCE_COMMIT)
    assert result["integrity"] == "FAILED"
    assert result["enrollment"] == "REJECTED"


def test_host_bundle_cannot_promote(tmp_path):
    capture = load(CAPTURE_PATH, "capture_device_evidence_host")
    verifier = load(VERIFY_PATH, "verify_device_evidence_host")
    evidence = android_evidence()
    evidence["status"] = "HOST_ONLY_NOT_DEVICE_EVIDENCE"
    evidence["physical_device_gate"] = "NOT_APPLICABLE_HOST"
    evidence["platform"]["android_detection"]["is_android"] = False
    capture.write_bundle(tmp_path, evidence)
    result = verifier.verify_bundle(tmp_path, expected_source_commit=SOURCE_COMMIT)
    assert result["enrollment"] == "REJECTED"


def test_inconsistent_profile_is_rejected(tmp_path):
    capture = load(CAPTURE_PATH, "capture_device_evidence_profile")
    verifier = load(VERIFY_PATH, "verify_device_evidence_profile")
    capture.write_bundle(tmp_path, android_evidence())
    report_path = tmp_path / "validation_report.json"
    report = capture.json.loads(report_path.read_text(encoding="utf-8"))
    report["device_profile"]["model"] = "different-model"
    report_path.write_text(capture.json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    manifest_path = tmp_path / "MANIFEST.sha256.json"
    manifest = capture.json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["validation_report.json"] = capture.sha256_file(report_path)
    manifest_path.write_text(capture.json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    result = verifier.verify_bundle(tmp_path, expected_source_commit=SOURCE_COMMIT)
    assert result["integrity"] == "VERIFIED"
    assert result["enrollment"] == "REJECTED"
    assert "device profile missing or inconsistent" in result["errors"]
