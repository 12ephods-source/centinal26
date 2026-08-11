from datetime import datetime, timedelta, timezone

import pytest

from centinal26.core import AuditLog, Engine, Grant, JobStore


def grant(capability: str, minutes: int = 5) -> Grant:
    return Grant(
        grant_id="test",
        capability=capability,
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(),
    )


def test_authorized_job_is_verified(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    engine = Engine(JobStore(tmp_path / "jobs.sqlite3"), audit)
    engine.register("test.echo", lambda value: value)
    job_id = engine.submit("test.echo", {"x": 1}, grant("test.echo"))
    assert engine.run_once() == job_id
    assert engine.store.counts() == {"verified": 1}
    assert audit.verify()


def test_mismatched_grant_is_denied(tmp_path):
    engine = Engine(JobStore(tmp_path / "jobs.sqlite3"), AuditLog(tmp_path / "audit.jsonl"))
    engine.register("test.echo", lambda value: value)
    with pytest.raises(PermissionError):
        engine.submit("test.echo", {}, grant("different.capability"))


def test_audit_tampering_is_detected(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    audit.append("event", {"truth": True})
    audit.path.write_text(audit.path.read_text().replace("true", "false"))
    assert not audit.verify()
