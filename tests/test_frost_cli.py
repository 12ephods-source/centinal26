from __future__ import annotations

from pathlib import Path

import pytest

from centinal26.event_state import EventStore, rebuild_state
from centinal26.frost_cli import classify_operator, run_operator


def _task(
    store: EventStore,
    task_id: str,
    capability: str = "system.echo",
    *,
    authority: str | None = None,
) -> None:
    payload = {
        "task_id": task_id,
        "objective": task_id,
        "capability": capability,
        "input": {"id": task_id},
    }
    if authority is not None:
        payload["authority"] = authority
    store.append("TASK_CREATED", payload, entity_id=task_id)


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
    assert classify_operator("Criticize") == "CRITIQUE"
    assert classify_operator("opposite opinion") == "CRITIQUE"
    assert classify_operator("fix everything") == "REPAIR"
    assert classify_operator("Automate") == "AUTOMATE"
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
    completed = [
        task_id for task_id, task in state.tasks.items() if task["status"] == "COMPLETE"
    ]
    assert len(completed) == 1


def test_autopilot_without_broad_authorize_runs_auto_safe_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1")
    store.close()

    result = run_operator("AUTOPILOT", authorize=False)

    assert result["advance"]["executed"] == ["t1"]
    assert result["advance"]["completed"] == ["t1"]
    assert result["advance"]["stop_reason"] == "COMPLETE"
    assert result["authorization_source"] is None

    state_store = EventStore(tmp_path / "events.sqlite3")
    events = state_store.events()
    state = rebuild_state(events)
    state_store.close()
    assert state.tasks["t1"]["status"] == "COMPLETE"
    authorized = [event for event in events if event.type == "TASK_AUTHORIZED"]
    assert authorized[0].payload["authorization_source"] == "capability_policy_auto_safe"


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


def test_critique_is_read_only_and_surfaces_blockers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1", authority="authorization_required")
    store.append(
        "BLOCKER_RECORDED",
        {
            "blocker_id": "b1",
            "task_id": "t1",
            "reason": "APPROVAL_REQUIRED",
            "detail": "explicit authorization required",
        },
        entity_id="b1",
    )
    before = store.count()
    store.close()

    result = run_operator("CRITIQUE")

    state_store = EventStore(tmp_path / "events.sqlite3")
    after = state_store.count()
    state_store.close()
    critique = result["critique"]
    assert before == after
    assert critique["promotion_authority"] is False
    assert critique["execution_authority"] is False
    assert any(issue["reason"] == "APPROVAL_REQUIRED" for issue in critique["issues"])


def test_repair_runs_safe_work_without_broad_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1")
    store.close()

    result = run_operator("REPAIR")

    assert result["advance"]["executed"] == ["t1"]
    assert result["advance"]["completed"] == ["t1"]
    assert result["advance"]["stop_reason"] == "COMPLETE"
    assert result["authorization_source"] == "safe_capability_policy_only"


def test_repair_does_not_bypass_adapter_style_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1", authority="authorization_required")
    store.close()

    result = run_operator("REPAIR")

    assert result["advance"]["executed"] == []
    assert result["advance"]["stop_reason"] == "APPROVAL_REQUIRED"


def test_automate_discovers_candidates_without_mutating_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, monkeypatch)
    _task(store, "t1", capability="missing.example")
    _task(store, "t2", capability="missing.example")
    before = store.count()
    store.close()

    result = run_operator("AUTOMATE")

    state_store = EventStore(tmp_path / "events.sqlite3")
    after = state_store.count()
    state_store.close()
    automation = result["automation"]
    assert before == after
    assert automation["promotion_authority"] is False
    assert automation["execution_authority"] is False
    assert len(automation["candidates"]) == 1
    assert automation["candidates"][0]["reasons"] == ["REPEATED_PATTERN"]
    assert automation["candidates"][0]["status"] == "CANDIDATE_ONLY"


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
