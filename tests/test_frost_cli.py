from __future__ import annotations

from pathlib import Path

import pytest

from centinal26.event_state import EventStore, rebuild_state
from centinal26.frost_cli import classify_operator, run_operator


def _task(store: EventStore, task_id: str, capability: str = "system.echo") -> None:
    store.append(
        "TASK_CREATED",
        {
            "task_id": task_id,
            "objective": task_id,
            "capability": capability,
            "input": {"id": task_id},
        },
        entity_id=task_id,
    )


def _dependency(store: EventStore, task_id: str, depends_on: str) -> None:
    store.append(
        "DEPENDENCY_ADDED",
        {"task_id": task_id, "depends_on": depends_on},
        entity_id=task_id,
    )


def _store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EventStore:
    monkeypatch.setenv("CENTINAL26_HOME", str(tmp_path))
    return EventStore(tmp_path / "events.sqlite3")


def test_classifier_maps_terse_execution_aliases() -> None:
    assert classify_operator("Proceed") == "PROCEED"
    assert classify_operator("implement") == "PROCEED"
    assert classify_operator("run it") == "PROCEED"
    assert classify_operator("Project   state") == "STATE"
    assert classify_operator("is that true") == "VERIFY"
    assert classify_operator("proceed automatically") == "AUTOPILOT"


def test_classifier_rejects_unimplemented_operator() -> None:
    with pytest.raises(ValueError, match="unsupported frost intent"):
        classify_operator("delete everything")


def test_proceed_is_explicit_authorization_for_exactly_one_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1")
    _task(store, "t2")
    store.close()

    result = run_operator("PROCEED")

    assert result["authorization_source"] == "explicit_frost_proceed_invocation"
    assert len(result["advance"]["executed"]) == 1
    assert result["advance"]["stop_reason"] == "RESOURCE_LIMIT"

    state_store = EventStore(tmp_path / "events.sqlite3")
    state = rebuild_state(state_store.events())
    state_store.close()
    completed = [task_id for task_id, task in state.tasks.items() if task["status"] == "COMPLETE"]
    assert len(completed) == 1


def test_autopilot_without_authorize_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1")
    store.close()

    result = run_operator("AUTOPILOT", authorize=False)

    assert result["advance"]["executed"] == []
    assert result["advance"]["stop_reason"] == "APPROVAL_REQUIRED"
    assert result["authorization_source"] is None

    state_store = EventStore(tmp_path / "events.sqlite3")
    state = rebuild_state(state_store.events())
    state_store.close()
    assert state.tasks["t1"]["status"] == "DISCOVERED"


def test_authorized_autopilot_completes_dependency_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1")
    _task(store, "t2")
    _dependency(store, "t2", "t1")
    store.close()

    result = run_operator("AUTOPILOT", authorize=True, max_tasks=10)

    assert result["advance"]["executed"] == ["t1", "t2"]
    assert result["advance"]["completed"] == ["t1", "t2"]
    assert result["advance"]["failed"] == []
    assert result["advance"]["stop_reason"] == "COMPLETE"
    assert result["authorization_source"] == "explicit_frost_autopilot_authorization"


def test_state_and_verify_are_read_only_operator_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1")
    before = store.count()
    store.close()

    state_result = run_operator("STATE")
    verify_result = run_operator("VERIFY")

    state_store = EventStore(tmp_path / "events.sqlite3")
    after = state_store.count()
    state_store.close()

    assert state_result["operator"] == "STATE"
    assert verify_result["event_chain_valid"] is True
    assert verify_result["runtime_audit_valid"] is True
    assert before == after


def test_autopilot_honors_task_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1")
    _task(store, "t2")
    store.close()

    result = run_operator("AUTOPILOT", authorize=True, max_tasks=1)

    assert len(result["advance"]["executed"]) == 1
    assert result["advance"]["stop_reason"] == "RESOURCE_LIMIT"


def test_max_tasks_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store(tmp_path, monkeypatch).close()
    with pytest.raises(ValueError, match="may not exceed 1000"):
        run_operator("AUTOPILOT", authorize=True, max_tasks=1001)
