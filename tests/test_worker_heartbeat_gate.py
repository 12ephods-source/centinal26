from datetime import UTC, datetime, timedelta

from automation.device.heartbeat import create_heartbeat
from automation.device.verify_worker_heartbeat import verify_heartbeat


def make_android_heartbeat(monkeypatch):
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    monkeypatch.setattr("automation.device.heartbeat.read_optional", lambda _: "boot-123")
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
