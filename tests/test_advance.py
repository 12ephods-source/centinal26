from __future__ import annotations

from pathlib import Path

from centinal26.advance import advance_until_idle, build_advance_engine
from centinal26.core import AuditLog
from centinal26.event_state import EventStore, rebuild_state
from centinal26.pipeline import AutomatedEngine, CapabilitySpec, EvidenceStore, RuntimeStore


def _task(store: EventStore, task_id: str, capability: str | None = "system.echo") -> None:
    payload = {"task_id": task_id, "objective": task_id, "input": {"id": task_id}}
    if capability is not None:
        payload["capability"] = capability
    store.append("TASK_CREATED", payload, entity_id=task_id)


def _dependency(store: EventStore, task_id: str, depends_on: str) -> None:
    store.append(
        "DEPENDENCY_ADDED",
        {"task_id": task_id, "depends_on": depends_on},
        entity_id=task_id,
    )


def test_advance_executes_dependency_chain_until_complete(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    _task(store, "t1")
    _task(store, "t2")
    _dependency(store, "t2", "t1")
    runtime = build_advance_engine(tmp_path)

    report = advance_until_idle(store, runtime, authorize=True)

    assert report.executed == ["t1", "t2"]
    assert report.completed == ["t1", "t2"]
    assert report.failed == []
    assert report.stop_reason == "COMPLETE"
    assert report.remaining_ready == []
    assert store.verify_chain()
    assert runtime.audit.verify()
    state = rebuild_state(store.events())
    assert state.tasks["t1"]["status"] == "COMPLETE"
    assert state.tasks["t2"]["status"] == "COMPLETE"


def test_advance_without_authorization_fails_closed_and_deduplicates_blocker(
    tmp_path: Path,
) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    _task(store, "t1")
    runtime = build_advance_engine(tmp_path)

    first = advance_until_idle(store, runtime, authorize=False)
    count_after_first = store.count()
    second = advance_until_idle(store, runtime, authorize=False)

    assert first.stop_reason == "APPROVAL_REQUIRED"
    assert second.stop_reason == "APPROVAL_REQUIRED"
    assert first.executed == []
    assert store.count() == count_after_first
    state = rebuild_state(store.events())
    assert len(state.blockers) == 1
    assert next(iter(state.blockers.values()))["reason"] == "APPROVAL_REQUIRED"
    assert state.tasks["t1"]["status"] == "DISCOVERED"


def test_advance_records_missing_capability_without_execution(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    _task(store, "t1", capability="missing.capability")
    runtime = build_advance_engine(tmp_path)

    report = advance_until_idle(store, runtime, authorize=True)

    assert report.stop_reason == "NO_CAPABILITY"
    assert report.executed == []
    assert report.blocked == {"t1": "NO_CAPABILITY"}
    state = rebuild_state(store.events())
    assert len(state.blockers) == 1


def test_verification_failure_is_terminal_and_blocks_dependents(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    _task(store, "t1", capability="test.bad")
    _task(store, "t2")
    _dependency(store, "t2", "t1")
    runtime = AutomatedEngine(
        RuntimeStore(tmp_path / "runtime.sqlite3"),
        AuditLog(tmp_path / "runtime-audit.jsonl"),
        EvidenceStore(tmp_path / "runtime-evidence"),
    )
    runtime.register(
        CapabilitySpec(
            name="test.bad",
            executor=lambda payload: {"value": payload},
            verifier=lambda _payload, _output: False,
            verifier_independent=True,
            max_attempts=1,
        )
    )

    report = advance_until_idle(store, runtime, authorize=True)

    assert report.executed == ["t1"]
    assert report.failed == ["t1"]
    assert report.stop_reason == "DEPENDENCY_BLOCKED"
    state = rebuild_state(store.events())
    assert state.tasks["t1"]["status"] == "VERIFICATION_FAILED"
    assert state.tasks["t2"]["status"] == "DISCOVERED"


def test_advance_honors_task_budget(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    _task(store, "t1")
    _task(store, "t2")
    runtime = build_advance_engine(tmp_path)

    report = advance_until_idle(store, runtime, authorize=True, max_tasks=1)

    assert len(report.executed) == 1
    assert report.stop_reason == "RESOURCE_LIMIT"
    assert len(report.remaining_ready) == 1


def test_non_independent_verifier_is_not_auto_executed(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    _task(store, "t1", capability="test.advisory")
    runtime = AutomatedEngine(
        RuntimeStore(tmp_path / "runtime.sqlite3"),
        AuditLog(tmp_path / "runtime-audit.jsonl"),
        EvidenceStore(tmp_path / "runtime-evidence"),
    )
    runtime.register(
        CapabilitySpec(
            name="test.advisory",
            executor=lambda payload: payload,
            verifier=lambda payload, output: payload == output,
            verifier_independent=False,
        )
    )

    report = advance_until_idle(store, runtime, authorize=True)

    assert report.executed == []
    assert report.stop_reason == "NO_CAPABILITY"
    assert report.blocked == {"t1": "VERIFIER_NOT_INDEPENDENT"}
