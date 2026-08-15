from __future__ import annotations

import json
from pathlib import Path

import pytest

from centinal26.event_state import EventStore, derive_ready_tasks, rebuild_state
from centinal26.ingest import discover_paths, ingest_bytes


def test_json_ingestion_builds_dependency_graph_and_is_idempotent(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "state.sqlite3")
    document = {
        "goals": [{"id": "g1", "title": "Automate the project"}],
        "tasks": [
            {"id": "t1", "objective": "Build the kernel"},
            {"id": "t2", "objective": "Run automation", "depends_on": ["t1"]},
        ],
        "decisions": [{"id": "d1", "text": "Use event sourcing"}],
        "blockers": [{"id": "b1", "text": "Physical Android gate"}],
        "artifacts": [{"id": "a1", "text": "release.zip", "sha256": "abc"}],
    }
    raw = json.dumps(document, sort_keys=True).encode()

    first = ingest_bytes(store, raw, name="project.json")
    second = ingest_bytes(store, raw, name="copy.json")

    assert first.duplicate is False
    assert first.events_appended == 8
    assert first.extracted == {
        "artifact": 1,
        "blocker": 1,
        "decision": 1,
        "dependency": 1,
        "goal": 1,
        "task": 2,
    }
    assert second.duplicate is True
    assert second.events_appended == 0
    assert store.count() == 8
    assert store.verify_chain()

    state = rebuild_state(store.events())
    task_by_external = {task["external_id"]: task_id for task_id, task in state.tasks.items()}
    assert derive_ready_tasks(state) == [task_by_external["t1"]]
    assert state.tasks[task_by_external["t2"]]["dependencies"] == [task_by_external["t1"]]


def test_text_ingestion_extracts_explicit_markers(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "state.sqlite3")
    text = b"""\
Ignored prose.
GOAL [g1]: Finish Automation OS
TASK [t1]: Build ingest
TASK [t2]: Build advance
DEPENDS: t2 -> t1
DECISION: Keep the reducer deterministic
BLOCKER: Physical phone validation
ARTIFACT: automation.zip
"""

    result = ingest_bytes(store, text, name="conversation.txt")
    state = rebuild_state(store.events())

    assert result.extracted["task"] == 2
    assert result.extracted["dependency"] == 1
    assert len(state.goals) == 1
    assert len(state.decisions) == 1
    assert len(state.blockers) == 1
    assert len(state.artifacts) == 1
    assert len(state.tasks) == 2


def test_invalid_dependency_fails_before_any_event_is_appended(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "state.sqlite3")
    raw = json.dumps(
        {
            "tasks": [{"id": "t1", "objective": "Valid task"}],
            "dependencies": [{"task": "missing", "depends_on": "t1"}],
        }
    ).encode()

    with pytest.raises(ValueError, match="unknown task id"):
        ingest_bytes(store, raw, name="invalid.json")

    assert store.count() == 0


def test_duplicate_entity_ids_fail_before_append(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "state.sqlite3")
    raw = json.dumps(
        {
            "tasks": [
                {"id": "same", "objective": "one"},
                {"id": "same", "objective": "two"},
            ]
        }
    ).encode()

    with pytest.raises(ValueError, match="duplicate task id"):
        ingest_bytes(store, raw, name="duplicate.json")

    assert store.count() == 0


def test_ingestion_is_bounded_by_source_size(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "state.sqlite3")
    with pytest.raises(ValueError, match="max_bytes"):
        ingest_bytes(store, b"12345", name="input.txt", max_bytes=4)
    assert store.count() == 0


def test_discover_paths_is_sorted_deduplicated_and_requires_recursive(tmp_path: Path) -> None:
    one = tmp_path / "b.txt"
    two = tmp_path / "a.txt"
    one.write_text("TASK: one", encoding="utf-8")
    two.write_text("TASK: two", encoding="utf-8")

    assert discover_paths([one, two, one]) == [two.resolve(), one.resolve()]
    with pytest.raises(IsADirectoryError):
        discover_paths([tmp_path])
    assert discover_paths([tmp_path], recursive=True) == [two.resolve(), one.resolve()]
