from __future__ import annotations

from datetime import UTC, datetime

import pytest

from automation.controller.outbound_queue import OutboundQueue, sign_record

DEVICE_ID = "android-1"
SOURCE_COMMIT = "a" * 40
ENROLLMENT_DIGEST = "b" * 64
SECRET = b"s" * 32


def _queue() -> OutboundQueue:
    queue = OutboundQueue(lambda device_id: SECRET if device_id == DEVICE_ID else b"")
    queue.register_device(
        device_id=DEVICE_ID,
        source_commit=SOURCE_COMMIT,
        enrollment_digest=ENROLLMENT_DIGEST,
        credential=SECRET,
    )
    return queue


def test_enqueue_is_signed_and_targeted() -> None:
    queue = _queue()
    job = queue.enqueue(device_id=DEVICE_ID, capability="diagnostic_status")
    assert job["target_device_id"] == DEVICE_ID
    assert job["expected_source_commit"] == SOURCE_COMMIT
    assert job["authorization_scope"] == {
        "device_id": DEVICE_ID,
        "capability": "diagnostic_status",
    }
    assert isinstance(job["signature"], str)


def test_arbitrary_capability_rejected() -> None:
    queue = _queue()
    with pytest.raises(ValueError, match="capability not allowed"):
        queue.enqueue(device_id=DEVICE_ID, capability="shell")


def test_unknown_device_rejected() -> None:
    queue = _queue()
    with pytest.raises(KeyError, match="device not registered"):
        queue.enqueue(device_id="other", capability="diagnostic_status")


def test_signed_result_acknowledges_once() -> None:
    queue = _queue()
    job = queue.enqueue(device_id=DEVICE_ID, capability="diagnostic_status")
    result = {
        "task_id": job["task_id"],
        "device_id": DEVICE_ID,
        "capability": "diagnostic_status",
        "status": "PASS",
        "timestamp": datetime.now(UTC).isoformat(),
        "source_commit": SOURCE_COMMIT,
        "output": {"ok": True},
        "previous_evidence_hash": "0" * 64,
    }
    result["signature"] = sign_record(result, SECRET)
    assert queue.accept_result(result)["status"] == "ACKNOWLEDGED"
    assert queue.accept_result(result)["status"] == "ALREADY_ACKNOWLEDGED"


def test_tampered_result_rejected() -> None:
    queue = _queue()
    job = queue.enqueue(device_id=DEVICE_ID, capability="inventory_snapshot")
    result = {
        "task_id": job["task_id"],
        "device_id": DEVICE_ID,
        "capability": "inventory_snapshot",
        "status": "PASS",
        "timestamp": datetime.now(UTC).isoformat(),
        "source_commit": SOURCE_COMMIT,
        "output": {"model": "test"},
        "previous_evidence_hash": "0" * 64,
        "signature": "0" * 64,
    }
    with pytest.raises(ValueError, match="invalid result signature"):
        queue.accept_result(result)
