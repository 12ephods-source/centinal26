from pathlib import Path

import pytest

from centinal26.event_state import EventStore, rebuild_state
from centinal26.intent_execution import (
    CapabilityRegistry,
    IntentExecutionController,
    IntentExecutionError,
)


def _registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(
        "test.increment",
        lambda payload: {"value": int(payload["value"]) + 1},
        lambda payload, output: output == {"value": int(payload["value"]) + 1},
    )
    return registry


def test_proceed_runs_full_vertical_slice(tmp_path: Path):
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        controller = IntentExecutionController(store, _registry())
        result = controller.ingest_and_execute(
            text="Proceed",
            adapter_id="hermes",
            external_id="vertical-001",
            capability="test.increment",
            payload={"value": 41},
            actor="user",
        )
        assert result.authorized
        assert result.executed
        assert result.verified
        assert result.completed
        assert result.event_chain_valid
        assert len(result.evidence_digest) == 64

        state = rebuild_state(store.events())
        assert state.tasks[result.task_id]["status"] == "COMPLETE"
        types = [event.type for event in store.events()]
        assert types == [
            "SOURCE_INGESTED",
            "TASK_CREATED",
            "TASK_AUTHORIZED",
            "TASK_STARTED",
            "TASK_EXECUTED",
            "VERIFICATION_PASSED",
            "TASK_COMPLETED",
        ]
    finally:
        store.close()


def test_embedded_proceed_is_not_authorization(tmp_path: Path):
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        controller = IntentExecutionController(store, _registry())
        with pytest.raises(IntentExecutionError, match="exact authorization"):
            controller.ingest_and_execute(
                text="Explain whether we should proceed after review",
                adapter_id="hermes",
                external_id="vertical-002",
                capability="test.increment",
                payload={"value": 1},
            )
        assert store.count() == 0
    finally:
        store.close()


def test_unregistered_capability_cannot_execute(tmp_path: Path):
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        controller = IntentExecutionController(store, _registry())
        with pytest.raises(IntentExecutionError, match="unregistered capability"):
            controller.ingest_and_execute(
                text="Proceed",
                adapter_id="hermes",
                external_id="vertical-003",
                capability="missing.capability",
                payload={},
            )
        state = rebuild_state(store.events())
        task = next(iter(state.tasks.values()))
        assert task["status"] == "DISCOVERED"
    finally:
        store.close()


def test_verification_failure_is_terminal(tmp_path: Path):
    registry = CapabilityRegistry()
    registry.register("test.bad", lambda payload: {"ok": False}, lambda payload, output: False)
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        controller = IntentExecutionController(store, registry)
        with pytest.raises(IntentExecutionError, match="verification failed"):
            controller.ingest_and_execute(
                text="Proceed",
                adapter_id="hermes",
                external_id="vertical-004",
                capability="test.bad",
                payload={},
            )
        state = rebuild_state(store.events())
        task = next(iter(state.tasks.values()))
        assert task["status"] == "VERIFICATION_FAILED"
        assert store.verify_chain()
    finally:
        store.close()
