import json
import sqlite3

import pytest

from centinal26 import event_state
from centinal26.event_state import (
    EVENT_SCHEMA_VERSION,
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


def test_append_rejects_lifecycle_event_for_unknown_task_without_poisoning_log(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")

    with pytest.raises(StateTransitionError, match="unknown task"):
        store.append("TASK_STARTED", {}, entity_id="missing")

    assert store.count() == 0
    assert store.verify_chain() is True


def test_duplicate_task_creation_is_rejected_before_persistence(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append("TASK_CREATED", {}, entity_id="task-1")

    with pytest.raises(StateTransitionError, match="task already exists"):
        store.append("TASK_CREATED", {}, entity_id="task-1")

    assert store.count() == 1
    assert store.verify_chain() is True


def test_illegal_verification_before_execution_is_rejected_before_persistence(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append("TASK_CREATED", {}, entity_id="task-1")

    with pytest.raises(StateTransitionError, match="illegal task transition"):
        store.append("VERIFICATION_PASSED", {}, entity_id="task-1")

    assert store.count() == 1
    assert rebuild_state(store.events()).tasks["task-1"]["status"] == "DISCOVERED"
    assert store.verify_chain() is True


def test_explicit_authorization_may_transition_directly_from_discovered(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append("TASK_CREATED", {}, entity_id="task-1")
    store.append("TASK_AUTHORIZED", {"source": "explicit-user"}, entity_id="task-1")
    store.append("TASK_STARTED", {}, entity_id="task-1")
    store.append("TASK_EXECUTED", {}, entity_id="task-1")
    store.append("VERIFICATION_PASSED", {}, entity_id="task-1")
    store.append("TASK_COMPLETED", {}, entity_id="task-1")

    assert rebuild_state(store.events()).tasks["task-1"]["status"] == "COMPLETE"
    assert store.verify_chain() is True


def test_terminal_task_cannot_be_resurrected(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append("TASK_CREATED", {}, entity_id="task-1")
    store.append("TASK_FAILED", {"reason": "bounded failure"}, entity_id="task-1")

    with pytest.raises(StateTransitionError, match="illegal task transition"):
        store.append("TASK_AUTHORIZED", {}, entity_id="task-1")

    assert rebuild_state(store.events()).tasks["task-1"]["status"] == "FAILED"
    assert store.verify_chain() is True


def test_dependencies_freeze_after_authorization_and_self_dependency_is_rejected(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    store.append("TASK_CREATED", {}, entity_id="task-1")
    store.append("TASK_CREATED", {}, entity_id="task-2")

    with pytest.raises(StateTransitionError, match="may not depend on itself"):
        store.append(
            "DEPENDENCY_ADDED",
            {"task_id": "task-1", "depends_on": "task-1"},
            entity_id="task-1",
        )

    store.append("TASK_AUTHORIZED", {}, entity_id="task-2")
    with pytest.raises(StateTransitionError, match="dependencies are frozen"):
        store.append(
            "DEPENDENCY_ADDED",
            {"task_id": "task-2", "depends_on": "task-1"},
            entity_id="task-2",
        )

    assert store.verify_chain() is True


def test_hash_valid_but_semantically_illegal_history_fails_chain_verification(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    created = store.append("TASK_CREATED", {}, entity_id="task-1")
    ts = event_state.now_iso()
    payload = {}
    bad_hash = event_state._event_hash(
        event_id="manual-illegal-event",
        ts=ts,
        event_type="VERIFICATION_PASSED",
        entity_id="task-1",
        payload=payload,
        prev_hash=created.event_hash,
    )
    store.db.execute(
        """INSERT INTO events (
            event_id, ts, type, entity_id, payload_json,
            prev_hash, event_hash, schema_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "manual-illegal-event",
            ts,
            "VERIFICATION_PASSED",
            "task-1",
            "{}",
            created.event_hash,
            bad_hash,
            EVENT_SCHEMA_VERSION,
        ),
    )
    store.db.commit()

    assert store.verify_chain() is False
