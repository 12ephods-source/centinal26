import json
from datetime import UTC, datetime, timedelta

import pytest

from centinal26.core import AuditLog, Engine, Grant, JobStore, Verification


def grant(capability: str, minutes: int = 5) -> Grant:
    return Grant(
        grant_id="test",
        capability=capability,
        expires_at=(datetime.now(UTC) + timedelta(minutes=minutes)).isoformat(),
    )


def exact_verifier(data: dict, output: dict) -> Verification:
    return Verification(
        passed=output == data,
        evidence={"method": "exact_match"},
    )


def test_authorized_job_is_verified(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    engine = Engine(JobStore(tmp_path / "jobs.sqlite3"), audit)
    engine.register("test.echo", lambda value: value, exact_verifier)
    job_id = engine.submit("test.echo", {"x": 1}, grant("test.echo"))
    assert engine.run_once() == job_id
    assert engine.store.counts() == {"verified": 1}
    assert audit.verify()


def test_execution_success_requires_verification(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    engine = Engine(JobStore(tmp_path / "jobs.sqlite3"), audit)
    engine.register(
        "test.echo",
        lambda value: value,
        lambda _data, _output: Verification(
            passed=False,
            evidence={"reason": "deliberate test rejection"},
        ),
    )
    job_id = engine.submit("test.echo", {"x": 1}, grant("test.echo"))

    assert engine.run_once() == job_id
    assert engine.store.counts() == {"verification_failed": 1}
    events = [
        json.loads(line)["event"]
        for line in audit.path.read_text(encoding="utf-8").splitlines()
    ]
    assert "job_executed" in events
    assert "job_verified" not in events
    assert "job_verification_failed" in events
    assert audit.verify()


def test_verifier_exception_fails_closed(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    engine = Engine(JobStore(tmp_path / "jobs.sqlite3"), audit)

    def broken_verifier(_data: dict, _output: dict) -> Verification:
        raise RuntimeError("verification unavailable")

    engine.register("test.echo", lambda value: value, broken_verifier)
    job_id = engine.submit("test.echo", {"x": 1}, grant("test.echo"))

    assert engine.run_once() == job_id
    assert engine.store.counts() == {"verification_failed": 1}
    assert audit.verify()


def test_mismatched_grant_is_denied(tmp_path):
    engine = Engine(JobStore(tmp_path / "jobs.sqlite3"), AuditLog(tmp_path / "audit.jsonl"))
    engine.register("test.echo", lambda value: value, exact_verifier)
    with pytest.raises(PermissionError):
        engine.submit("test.echo", {}, grant("different.capability"))


def test_audit_tampering_is_detected(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    audit.append("event", {"truth": True})
    audit.path.write_text(audit.path.read_text().replace("true", "false"))
    assert not audit.verify()
