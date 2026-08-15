import json
import sqlite3

import pytest

from centinal26.event_state import (
    EventStore,
    StateTransitionError,
    derive_ready_tasks,
    rebuild_state,
)


def test_hash_chain_replay_and_ready_task_derivation(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append("SOURCE_INGESTED", {"kind": "conversation"}, entity_id="source-1")
    store.append("GOAL_DISCOVERED", {"title": "close automation loop"}, entity_id="goal-1")
    store.append("TASK_CREATED", {"objective": "build kernel"}, entity_id="task-1")
    store.append("TASK_CREATED", {"objective": "build ingestor"}, entity_id="task-2")
    store.append(
        "DEPENDENCY_ADDED",
        {"task_id": "task-2", "depends_on": "task-1"},
        entity_id="task-2",
    )

    initial = rebuild_state(store.events())
    assert derive_ready_tasks(initial) == ["task-1"]

    store.append("TASK_READY", {}, entity_id="task-1")
    store.append("TASK_AUTHORIZED", {"grant": "g-1"}, entity_id="task-1")
    store.append("TASK_STARTED", {}, entity_id="task-1")
    store.append("TASK_EXECUTED", {"exit_code": 0}, entity_id="task-1")
    store.append("VERIFICATION_PASSED", {"method": "pytest"}, entity_id="task-1")
    store.append("ARTIFACT_CREATED", {"sha256": "abc"}, entity_id="artifact-1")
    store.append("TASK_COMPLETED", {}, entity_id="task-1")

    expected = rebuild_state(store.events()).as_dict()
    expected_json = json.dumps(expected, sort_keys=True, separators=(",", ":"))

    assert store.verify_chain() is True
    assert derive_ready_tasks(rebuild_state(store.events())) == ["task-2"]

    store.close()
    reopened = EventStore(tmp_path / "events.sqlite3")
    rebuilt_json = json.dumps(
        rebuild_state(reopened.events()).as_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )
    assert rebuilt_json == expected_json
    assert reopened.verify_chain() is True


def test_events_table_rejects_update_and_delete(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    event = store.append("TASK_CREATED", {"objective": "immutable"}, entity_id="task-1")

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.db.execute("UPDATE events SET type='TASK_FAILED' WHERE seq=?", (event.seq,))
    store.db.rollback()

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.db.execute("DELETE FROM events WHERE seq=?", (event.seq,))
    store.db.rollback()

    assert store.verify_chain() is True


def test_chain_verifier_detects_tampering_even_if_database_guard_is_removed(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append("TASK_CREATED", {"objective": "detect tamper"}, entity_id="task-1")
    store.append("TASK_READY", {}, entity_id="task-1")

    store.db.execute("DROP TRIGGER events_no_update")
    store.db.execute("UPDATE events SET payload_json='{}' WHERE seq=1")
    store.db.commit()

    assert store.verify_chain() is False


def test_reducer_rejects_lifecycle_event_for_unknown_task(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append("TASK_STARTED", {}, entity_id="missing")

    with pytest.raises(StateTransitionError, match="unknown task"):
        rebuild_state(store.events())


def test_duplicate_task_creation_is_invalid_history(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append("TASK_CREATED", {}, entity_id="task-1")
    store.append("TASK_CREATED", {}, entity_id="task-1")

    with pytest.raises(StateTransitionError, match="task already exists"):
        rebuild_state(store.events())
