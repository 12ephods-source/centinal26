from __future__ import annotations

from centinal26.event_state import EventStore, rebuild_state
from centinal26.improvement_cycle import (
    _candidate,
    _rank_runnable,
    advance_ranked_until_idle,
)


def test_rank_runnable_prefers_high_value_task():
    tasks = {
        "low": {
            "capability": "system.echo",
            "expected_value": 1.0,
            "execution_cost": 1.0,
        },
        "high": {
            "capability": "system.echo",
            "expected_value": 5.0,
            "dependency_unlock": 2.0,
        },
    }
    ranked = _rank_runnable(
        [("low", "auto"), ("high", "auto")],
        tasks,
    )
    assert [task_id for task_id, _ in ranked] == ["high", "low"]


def test_candidate_ignores_non_numeric_metrics():
    task = {
        "capability": "system.echo",
        "expected_value": "not-a-number",
        "execution_risk": None,
    }
    candidate = _candidate("task-1", task)
    assert candidate.expected_value == 0.0
    assert candidate.execution_risk == 0.0


def test_ranked_cycle_executes_best_ready_task_first(tmp_path, monkeypatch):
    import centinal26.improvement_cycle as module

    monkeypatch.setattr(module, "state_home", lambda: tmp_path / "runtime")
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        store.append(
            "TASK_CREATED",
            {
                "task_id": "task-low",
                "capability": "system.echo",
                "input": {"value": "low"},
                "expected_value": 1.0,
            },
            entity_id="task-low",
        )
        store.append(
            "TASK_CREATED",
            {
                "task_id": "task-high",
                "capability": "system.echo",
                "input": {"value": "high"},
                "expected_value": 8.0,
                "dependency_unlock": 3.0,
            },
            entity_id="task-high",
        )

        report = advance_ranked_until_idle(store, max_tasks=1)
        assert report.executed == ["task-high"]
        assert report.completed == ["task-high"]
        assert report.remaining_ready == ["task-low"]

        state = rebuild_state(store.events())
        assert state.tasks["task-high"]["status"] == "COMPLETE"
        assert state.tasks["task-low"]["status"] != "COMPLETE"
    finally:
        store.close()


def test_ranked_cycle_fails_closed_on_unknown_capability(tmp_path, monkeypatch):
    import centinal26.improvement_cycle as module

    monkeypatch.setattr(module, "state_home", lambda: tmp_path / "runtime")
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        store.append(
            "TASK_CREATED",
            {
                "task_id": "unknown",
                "capability": "unregistered.capability",
                "input": {},
                "expected_value": 999.0,
            },
            entity_id="unknown",
        )
        report = advance_ranked_until_idle(store, max_tasks=1)
        assert report.executed == []
        assert report.blocked == {"unknown": "NO_CAPABILITY"}
        assert report.stop_reason == "NO_CAPABILITY"
    finally:
        store.close()


def test_ranked_cycle_rejects_excessive_work_limit(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        try:
            advance_ranked_until_idle(store, max_tasks=1001)
        except ValueError as error:
            assert "may not exceed 1000" in str(error)
        else:
            raise AssertionError("expected ValueError")
    finally:
        store.close()
