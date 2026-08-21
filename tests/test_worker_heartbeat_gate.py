from datetime import UTC, datetime, timedelta
from importlib import util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEARTBEAT_PATH = ROOT / "automation" / "device" / "heartbeat.py"
VERIFY_PATH = ROOT / "automation" / "device" / "verify_worker_heartbeat.py"


def load_module(name: str, path: Path):
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


heartbeat_module = load_module("worker_heartbeat", HEARTBEAT_PATH)
verify_module = load_module("verify_worker_heartbeat", VERIFY_PATH)
create_heartbeat = heartbeat_module.create_heartbeat
verify_heartbeat = verify_module.verify_heartbeat


def make_android_heartbeat(monkeypatch):
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    monkeypatch.setattr(heartbeat_module, "read_optional", lambda _: "boot-123")
    return create_heartbeat("phone-1", "enroll-digest", sequence=7)


def test_verified_fresh_heartbeat_is_activation_eligible(monkeypatch):
    heartbeat = make_android_heartbeat(monkeypatch)
    now = datetime.fromisoformat(heartbeat["timestamp"])
    result = verify_heartbeat(
        heartbeat,
        expected_device_id="phone-1",
        expected_enrollment_digest="enroll-digest",
        expected_boot_id="boot-123",
        now=now,
    )
    assert result["eligible"] is True
    assert result["worker_activation"] == "VERIFIED_ACTIVE_ELIGIBLE"


def test_tampered_heartbeat_is_rejected(monkeypatch):
    heartbeat = make_android_heartbeat(monkeypatch)
    heartbeat["sequence"] = 8
    now = datetime.fromisoformat(heartbeat["timestamp"])
    result = verify_heartbeat(
        heartbeat,
        expected_device_id="phone-1",
        expected_enrollment_digest="enroll-digest",
        expected_boot_id="boot-123",
        now=now,
    )
    assert "RECORD_HASH_MISMATCH" in result["errors"]


def test_stale_heartbeat_is_rejected(monkeypatch):
    heartbeat = make_android_heartbeat(monkeypatch)
    now = datetime.fromisoformat(heartbeat["timestamp"]) + timedelta(minutes=10)
    result = verify_heartbeat(
        heartbeat,
        expected_device_id="phone-1",
        expected_enrollment_digest="enroll-digest",
        expected_boot_id="boot-123",
        now=now.astimezone(UTC),
    )
    assert "HEARTBEAT_STALE" in result["errors"]


def test_wrong_boot_binding_is_rejected(monkeypatch):
    heartbeat = make_android_heartbeat(monkeypatch)
    now = datetime.fromisoformat(heartbeat["timestamp"])
    result = verify_heartbeat(
        heartbeat,
        expected_device_id="phone-1",
        expected_enrollment_digest="enroll-digest",
        expected_boot_id="different-boot",
        now=now,
    )
    assert "BOOT_ID_MISMATCH" in result["errors"]
