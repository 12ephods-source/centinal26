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
    source_commit = "a" * 40
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    evidence = module.collect("android-test", source_commit=source_commit)
    assert evidence["status"] == "DEVICE_EVIDENCE_CAPTURED"
    assert evidence["physical_device_gate"] == "EVIDENCE_CAPTURED_UNVERIFIED"
    assert evidence["software_provenance"]["source_commit"] == source_commit
    assert evidence["claims"]["device_origin"] == "OBSERVED"
    assert evidence["claims"]["software_provenance"] == "OBSERVED"
    assert evidence["claims"]["device_profile"] == "OBSERVED_UNVERIFIED"
    assert evidence["claims"]["enrollment"] == "PENDING_CONTROLLER_VERIFICATION"


def test_normalized_device_profile_parses_termux_and_getprop(monkeypatch):
    module = load_module()
    monkeypatch.setenv("TERMUX_VERSION", "googleplay.2026.06.21")
    monkeypatch.setenv("TERMUX__USER_ID", "0")
    commands = {
        "uname": {"returncode": 0, "stdout": "Linux localhost kernel aarch64 Android\n"},
        "getprop": {
            "returncode": 0,
            "stdout": (
                "[ro.product.manufacturer]: [samsung]\n"
                "[ro.product.model]: [SM-A155M]\n"
                "[ro.build.version.release]: [16]\n"
                "[ro.build.version.sdk]: [36]\n"
            ),
        },
        "termux_info": {
            "returncode": 0,
            "stdout": (
                "Packages CPU architecture:\n"
                "aarch64\n"
                "termux-tools version:\n"
                "3.0.9\n"
            ),
        },
    }
    profile = module.normalized_device_profile(commands)
    assert profile["manufacturer"] == "samsung"
    assert profile["model"] == "SM-A155M"
    assert profile["android_version"] == "16"
    assert profile["android_sdk"] == "36"
    assert profile["cpu_architecture"] == "aarch64"
    assert profile["termux_version"] == "googleplay.2026.06.21"
    assert profile["termux_tools_version"] == "3.0.9"
    assert profile["termux_user_id"] == "0"


def test_bundle_manifest_hashes_are_self_consistent(tmp_path):
    module = load_module()
    source_commit = "b" * 40
    evidence = {
        "device_id": "test-device",
        "captured_at_utc": "2026-08-21T00:00:00+00:00",
        "status": "DEVICE_EVIDENCE_CAPTURED",
        "physical_device_gate": "EVIDENCE_CAPTURED_UNVERIFIED",
        "software_provenance": {"source_commit": source_commit},
        "device_profile": {"model": "test-model"},
        "package_inventory_sources": ["android_packages_pm"],
    }
    module.write_bundle(tmp_path, evidence)
    manifest = module.json.loads((tmp_path / "MANIFEST.sha256.json").read_text())
    report = module.json.loads((tmp_path / "validation_report.json").read_text())
    assert report["source_commit"] == source_commit
    assert report["device_profile"] == {"model": "test-model"}
    assert set(manifest["files"]) == {"device_evidence.json", "validation_report.json"}
    for name, expected in manifest["files"].items():
        assert module.sha256_file(tmp_path / name) == expected
