from importlib import util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_PATH = (
    ROOT
    / "automation"
    / "deployment"
    / "enrollment_package"
    / "capture_device_evidence.py"
)
VERIFY_PATH = (
    ROOT
    / "automation"
    / "deployment"
    / "enrollment_package"
    / "verify_device_evidence.py"
)


def load_module(name: str, path: Path):
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_bundle(tmp_path: Path, source_commit: str) -> None:
    capture = load_module("capture_device_evidence_provenance", CAPTURE_PATH)
    evidence = {
        "schema_version": "1.2",
        "device_id": "phone-1",
        "captured_at_utc": "2026-08-21T00:00:00+00:00",
        "status": "DEVICE_EVIDENCE_CAPTURED",
        "physical_device_gate": "EVIDENCE_CAPTURED_UNVERIFIED",
        "software_provenance": {
            "repository": "12ephods-source/centinal26",
            "source_commit": source_commit,
            "status": "OBSERVED",
        },
        "platform": {
            "android_detection": {
                "is_android": True,
                "signals": {
                    "ANDROID_ROOT": "/system",
                    "ANDROID_DATA": "/data",
                    "system_build_prop": True,
                    "termux_prefix": True,
                },
            },
            "boot_id": "boot-123",
        },
        "device_profile": {
            "manufacturer": "samsung",
            "model": "SM-A155M",
            "android_version": "16",
            "cpu_architecture": "aarch64",
        },
        "package_inventory_sources": ["android_packages_pm"],
    }
    capture.write_bundle(tmp_path, evidence)


def test_expected_source_commit_is_verified(tmp_path):
    source_commit = "1" * 40
    make_bundle(tmp_path, source_commit)
    verifier = load_module("verify_device_evidence_expected", VERIFY_PATH)

    result = verifier.verify_bundle(
        tmp_path,
        expected_source_commit=source_commit,
    )

    expected_digest = verifier.sha256_file(tmp_path / "MANIFEST.sha256.json")
    assert result["software_provenance"] == "VERIFIED_EXPECTED_COMMIT"
    assert result["source_commit"] == source_commit
    assert result["device_profile"]["model"] == "SM-A155M"
    assert result["enrollment_digest"] == expected_digest
    assert result["enrollment"] == "VERIFIED_ELIGIBLE"


def test_wrong_source_commit_is_rejected_even_with_valid_manifest(tmp_path):
    make_bundle(tmp_path, "2" * 40)
    verifier = load_module("verify_device_evidence_mismatch", VERIFY_PATH)

    result = verifier.verify_bundle(
        tmp_path,
        expected_source_commit="3" * 40,
    )

    assert result["integrity"] == "VERIFIED"
    assert result["enrollment"] == "REJECTED"
    assert result["software_provenance"] == "UNVERIFIED"
    assert "enrollment_digest" not in result
    assert result["errors"] == [
        {
            "source_commit_mismatch": {
                "expected": "3" * 40,
                "observed": "2" * 40,
            }
        }
    ]


def test_missing_source_commit_is_rejected(tmp_path):
    make_bundle(tmp_path, "4" * 40)
    evidence_path = tmp_path / "device_evidence.json"
    capture = load_module("capture_device_evidence_missing", CAPTURE_PATH)
    evidence = capture.json.loads(evidence_path.read_text())
    evidence["software_provenance"]["source_commit"] = None
    capture.write_bundle(tmp_path, evidence)
    verifier = load_module("verify_device_evidence_missing", VERIFY_PATH)

    result = verifier.verify_bundle(tmp_path, expected_source_commit="4" * 40)

    assert result["enrollment"] == "REJECTED"
    assert "software source commit provenance missing or inconsistent" in result["errors"]
