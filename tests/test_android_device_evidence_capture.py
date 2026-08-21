from importlib import util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "automation"
    / "deployment"
    / "enrollment_package"
    / "capture_device_evidence.py"
)


def load_module():
    spec = util.spec_from_file_location("capture_device_evidence", MODULE_PATH)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_host_execution_cannot_claim_physical_device(monkeypatch):
    module = load_module()
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.delenv("ANDROID_DATA", raising=False)
    monkeypatch.setenv("PREFIX", "/usr")
    monkeypatch.setattr(module.Path, "exists", lambda self: False)
    evidence = module.collect("host-test")
    assert evidence["status"] == "HOST_ONLY_NOT_DEVICE_EVIDENCE"
    assert evidence["physical_device_gate"] == "NOT_APPLICABLE_HOST"
    assert evidence["claims"]["device_origin"] == "FAILED"


def test_android_signal_records_unverified_device_evidence(monkeypatch):
    module = load_module()
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    evidence = module.collect("android-test")
    assert evidence["status"] == "DEVICE_EVIDENCE_CAPTURED"
    assert evidence["physical_device_gate"] == "EVIDENCE_CAPTURED_UNVERIFIED"
    assert evidence["claims"]["device_origin"] == "OBSERVED"
    assert evidence["claims"]["enrollment"] == "PENDING_CONTROLLER_VERIFICATION"


def test_bundle_manifest_hashes_are_self_consistent(tmp_path):
    module = load_module()
    evidence = {
        "device_id": "test-device",
        "captured_at_utc": "2026-08-21T00:00:00+00:00",
        "status": "DEVICE_EVIDENCE_CAPTURED",
        "physical_device_gate": "EVIDENCE_CAPTURED_UNVERIFIED",
        "package_inventory_sources": ["android_packages_pm"],
    }
    module.write_bundle(tmp_path, evidence)
    manifest = module.json.loads((tmp_path / "MANIFEST.sha256.json").read_text())
    assert set(manifest["files"]) == {"device_evidence.json", "validation_report.json"}
    for name, expected in manifest["files"].items():
        assert module.sha256_file(tmp_path / name) == expected
