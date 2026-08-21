from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from automation.device.outbound_worker import Journal, Worker, WorkerConfig, sign_record


def _worker(tmp_path: Path) -> Worker:
    secret = tmp_path / "secret"
    secret.write_bytes(b"x" * 32)
    secret.chmod(0o600)
    config = WorkerConfig(
        device_id="device-1",
        source_commit="a" * 40,
        queue_url="https://controller.invalid/queue",
        result_url="https://controller.invalid/results",
        credential_path=secret,
        state_dir=tmp_path / "state",
        poll_seconds=1,
        max_backoff_seconds=4,
    )
    return Worker(config)


def _job(worker: Worker, **overrides) -> dict:
    job = {
        "task_id": "task-1",
        "target_device_id": "device-1",
        "capability": "diagnostic_status",
        "parameters": {},
        "authorization_scope": {
            "device_id": "device-1",
            "capability": "diagnostic_status",
        },
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "nonce": "nonce-1",
        "expected_source_commit": "a" * 40,
        "signature": "",
    }
    job.update(overrides)
    job["signature"] = sign_record(job, worker.secret)
    return job


def test_valid_bounded_job_executes_and_replay_fails(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    job = _job(worker)
    first = worker.execute_job(job)
    assert first["status"] == "PASS"
    assert first["capability"] == "diagnostic_status"
    assert worker.execute_job(job)["errors"] == ["NONCE_REPLAY"]


def test_arbitrary_capability_rejected(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    job = _job(
        worker,
        capability="shell",
        authorization_scope={"device_id": "device-1", "capability": "shell"},
    )
    assert "CAPABILITY_NOT_ALLOWED" in worker.validate_job(job)


def test_wrong_device_expired_and_wrong_source_rejected(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    job = _job(
        worker,
        target_device_id="other",
        expected_source_commit="b" * 40,
        expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    )
    errors = worker.validate_job(job)
    assert "DEVICE_TARGET_MISMATCH" in errors
    assert "SOURCE_COMMIT_MISMATCH" in errors
    assert "JOB_EXPIRED" in errors


def test_tampered_job_signature_rejected(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    job = _job(worker)
    job["parameters"] = {"tampered": True}
    assert "SIGNATURE_INVALID" in worker.validate_job(job)


def test_credential_permissions_fail_closed(tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    secret.write_bytes(b"x" * 32)
    secret.chmod(0o644)
    config = WorkerConfig(
        device_id="device-1",
        source_commit="a" * 40,
        queue_url="https://controller.invalid/queue",
        result_url="https://controller.invalid/results",
        credential_path=secret,
        state_dir=tmp_path / "state",
    )
    try:
        Worker(config)
    except PermissionError:
        pass
    else:
        raise AssertionError("world-readable credential was accepted")


def test_journal_is_hash_chained_and_append_only(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    first = journal.append({"event": "first"})
    second = journal.append({"event": "second"})
    assert first["previous_hash"] == "0" * 64
    assert second["previous_hash"] == first["record_hash"]
    records = [json.loads(line) for line in journal.path.read_text().splitlines()]
    assert [record["event"] for record in records] == ["first", "second"]


def test_result_is_signed_and_bound_to_previous_evidence(tmp_path: Path) -> None:
    worker = _worker(tmp_path)
    worker.journal.append({"event": "prior"})
    previous = worker.journal.tail_hash()
    result = worker.execute_job(_job(worker))
    assert result["previous_evidence_hash"] == previous
    assert len(result["signature"]) == 64


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "worker.json"
    value = {
        "device_id": "d",
        "source_commit": "a" * 40,
        "queue_url": "https://q.invalid",
        "result_url": "https://r.invalid",
        "credential_path": str(tmp_path / "secret"),
        "state_dir": str(tmp_path / "state"),
        "poll_seconds": 12,
        "max_backoff_seconds": 99,
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    config = WorkerConfig.from_json(path)
    assert config.device_id == "d"
    assert config.poll_seconds == 12
    assert os.fspath(config.state_dir) == value["state_dir"]
