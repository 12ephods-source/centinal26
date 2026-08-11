import json
from datetime import UTC, datetime, timedelta

from centinal26.core import AuditLog, Grant
from centinal26.pipeline import (
    AutomatedEngine,
    CapabilitySpec,
    EvidenceStore,
    Intent,
    RuntimeStore,
    echo_reducer,
    echo_verifier,
)


def grant(name: str) -> Grant:
    return Grant("test-grant", name, (datetime.now(UTC) + timedelta(minutes=5)).isoformat())


def runtime(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    audit = AuditLog(tmp_path / "audit.jsonl")
    evidence = EvidenceStore(tmp_path / "evidence")
    engine = AutomatedEngine(store, audit, evidence)
    engine.register(
        CapabilitySpec(
            name="system.echo",
            executor=lambda payload: {"echo": payload},
            verifier=echo_verifier,
            reducer=echo_reducer,
            verifier_independent=True,
        )
    )
    return engine


def test_full_vertical_slice_commits_state_only_after_verification(tmp_path):
    engine = runtime(tmp_path)
    intent = Intent("system.echo", {"message": "online"})
    job_id = engine.submit(intent, grant("system.echo"), idempotency_key="slice-1")
    assert engine.run_once() == job_id
    row = engine.store.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert row["state"] == "verified"
    assert engine.store.get_state("system.echo")["verified_runs"] == 1
    assert engine.audit.verify()
    assert all(
        engine.evidence.verify(path)
        for path in (engine.evidence.root / job_id).glob("*.json")
    )


def test_idempotency_collapses_duplicate_submissions(tmp_path):
    engine = runtime(tmp_path)
    intent = Intent("system.echo", {"x": 1})
    first = engine.submit(intent, grant("system.echo"), idempotency_key="same")
    second = engine.submit(intent, grant("system.echo"), idempotency_key="same")
    assert first == second
    count = engine.store.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert count == 1


def test_verifier_failure_blocks_state_update(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    engine = AutomatedEngine(
        store, AuditLog(tmp_path / "audit.jsonl"), EvidenceStore(tmp_path / "evidence")
    )
    engine.register(
        CapabilitySpec(
            name="bad.echo",
            executor=lambda payload: {"echo": payload},
            verifier=lambda _payload, _output: False,
            reducer=echo_reducer,
        )
    )
    job_id = engine.submit(
        Intent("bad.echo", {"x": 1}), grant("bad.echo"), idempotency_key="bad"
    )
    engine.run_once()
    row = store.db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert row["state"] == "failed_verification"
    assert store.get_state("bad.echo") is None


def test_failed_execution_retries_then_fails(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    engine = AutomatedEngine(
        store, AuditLog(tmp_path / "audit.jsonl"), EvidenceStore(tmp_path / "evidence")
    )

    def explode(_payload):
        raise RuntimeError("boom")

    engine.register(
        CapabilitySpec(
            name="test.fail",
            executor=explode,
            verifier=lambda _payload, _output: True,
            max_attempts=2,
        )
    )
    job_id = engine.submit(
        Intent("test.fail", {}), grant("test.fail"), idempotency_key="fail"
    )
    engine.run_once()
    state = store.db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
    assert state == "queued"
    engine.run_once()
    state = store.db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
    assert state == "failed"
    assert len(list((engine.evidence.root / job_id).glob("*.json"))) == 2


def test_expired_lease_is_recovered(tmp_path):
    engine = runtime(tmp_path)
    job_id = engine.submit(
        Intent("system.echo", {"x": 1}), grant("system.echo"), idempotency_key="lease"
    )
    row = engine.store.claim(lease_seconds=60)
    assert row["id"] == job_id
    engine.store.db.execute(
        "UPDATE jobs SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?", (job_id,)
    )
    engine.store.db.commit()
    assert engine.store.recover() == 1
    state = engine.store.db.execute(
        "SELECT state FROM jobs WHERE id=?", (job_id,)
    ).fetchone()[0]
    assert state == "queued"


def test_evidence_tamper_is_detected(tmp_path):
    engine = runtime(tmp_path)
    job_id = engine.submit(
        Intent("system.echo", {"x": 1}), grant("system.echo"), idempotency_key="evidence"
    )
    engine.run_once()
    path = next((engine.evidence.root / job_id).glob("*.json"))
    data = json.loads(path.read_text())
    data["output"] = {"tampered": True}
    path.write_text(json.dumps(data))
    assert not engine.evidence.verify(path)


def test_evolution_gate_stays_closed_without_recovery_evidence(tmp_path):
    engine = runtime(tmp_path)
    for i in range(3):
        engine.submit(
            Intent("system.echo", {"i": i}), grant("system.echo"), idempotency_key=f"evo-{i}"
        )
        engine.run_once()
    status = engine.store.evolution_status(3)
    assert status["consecutive_passes"] == 3
    assert not status["ready"]
    assert not status["recovery_pass"]


def test_timeout_is_bounded_and_retried(tmp_path):
    import time

    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    engine = AutomatedEngine(
        store, AuditLog(tmp_path / "audit.jsonl"), EvidenceStore(tmp_path / "evidence")
    )

    def slow(_payload):
        time.sleep(0.2)
        return {"ok": True}

    engine.register(
        CapabilitySpec(
            name="test.slow",
            executor=slow,
            verifier=lambda _payload, _output: True,
            timeout_seconds=0.02,
            max_attempts=1,
        )
    )
    job_id = engine.submit(
        Intent("test.slow", {}), grant("test.slow"), idempotency_key="slow"
    )
    engine.run_once()
    row = store.db.execute("SELECT state,result FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert row["state"] == "failed"
    assert "TimeoutError" in row["result"]


def test_evolution_gate_can_open_after_recovery_and_independent_verification(tmp_path):
    engine = runtime(tmp_path)
    for i in range(3):
        engine.submit(
            Intent("system.echo", {"i": i}), grant("system.echo"), idempotency_key=f"open-{i}"
        )
        engine.run_once(recovery_test=(i == 2))
    status = engine.store.evolution_status(3)
    assert status["ready"]


def test_state_divergence_is_detected_and_closes_evolution_gate(tmp_path, monkeypatch):
    engine = runtime(tmp_path)
    original_get_state = engine.store.get_state
    reads = {"count": 0}

    def divergent_readback(key):
        reads["count"] += 1
        if reads["count"] == 1:
            return original_get_state(key)
        return {"corrupt": True}

    monkeypatch.setattr(engine.store, "get_state", divergent_readback)
    job_id = engine.submit(
        Intent("system.echo", {"x": 1}),
        grant("system.echo"),
        idempotency_key="divergence",
    )
    engine.run_once()
    row = engine.store.db.execute(
        "SELECT state,evidence_path FROM jobs WHERE id=?", (job_id,)
    ).fetchone()
    assert row["state"] == "state_diverged"
    evidence_path = engine.evidence.root.parent / row["evidence_path"]
    if not evidence_path.exists():
        evidence_path = engine.evidence.root / job_id / "0001-state-divergence.json"
    assert engine.evidence.verify(evidence_path)
    status = engine.store.evolution_status(1)
    assert not status["ready"]
    assert not status["zero_state_divergence"]
