from __future__ import annotations

import json
from pathlib import Path

import pytest

from centinal26.adapter_gateway import (
    CANONICAL_ADAPTER_IDS,
    AdapterRequest,
    AdapterRequestConflict,
    CanonicalAdapterGateway,
)
from centinal26.advance import advance_until_idle, build_advance_engine
from centinal26.event_state import EventStore, derive_ready_tasks, rebuild_state


@pytest.mark.parametrize("adapter_id", sorted(CANONICAL_ADAPTER_IDS))
def test_every_domain_adapter_normalizes_to_one_canonical_task(
    tmp_path: Path, adapter_id: str
) -> None:
    store = EventStore(tmp_path / f"{adapter_id}.sqlite3")
    gateway = CanonicalAdapterGateway(store)
    request = AdapterRequest(
        adapter_id=adapter_id,
        external_id="request-42",
        capability="system.echo",
        payload={"message": adapter_id},
        constraints={"max_runtime_seconds": 30},
        objective=f"echo from {adapter_id}",
    )

    first = gateway.ingest(request)
    second = gateway.ingest(request)

    assert first.events_appended == 2
    assert first.duplicate is False
    assert second.events_appended == 0
    assert second.duplicate is True
    assert second.request_id == first.request_id
    assert second.task_id == first.task_id
    assert store.verify_chain()

    state = rebuild_state(store.events())
    assert list(state.sources) == [first.request_id]
    assert list(state.tasks) == [first.task_id]
    assert state.sources[first.request_id]["authority"] == "proposal_only"
    assert state.tasks[first.task_id]["authority"] == "authorization_required"
    assert state.tasks[first.task_id]["source_id"] == first.request_id
    assert state.tasks[first.task_id]["request_sha256"] == first.request_sha256
    assert derive_ready_tasks(state) == [first.task_id]


def test_adapter_request_identity_conflict_is_fail_closed(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    gateway = CanonicalAdapterGateway(store)
    first = AdapterRequest("base44", "job-1", "system.echo", {"value": 1})
    gateway.ingest(first)
    event_count = store.count()

    with pytest.raises(AdapterRequestConflict, match="different content"):
        gateway.ingest(AdapterRequest("base44", "job-1", "system.echo", {"value": 2}))

    assert store.count() == event_count
    assert store.verify_chain()


def test_unknown_adapter_is_rejected_before_canonical_state_changes(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    gateway = CanonicalAdapterGateway(store)

    with pytest.raises(ValueError, match="unsupported canonical adapter"):
        gateway.ingest(AdapterRequest("unknown", "x", "system.echo", {}))

    assert store.count() == 0


def test_adapter_cannot_bypass_explicit_authorization(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    gateway = CanonicalAdapterGateway(store)
    result = gateway.ingest(
        AdapterRequest(
            "discord",
            "message-1",
            "system.echo",
            {
                "message": "proposal only",
                "authorize": True,
                "grant": {"capability": "*"},
            },
        )
    )
    runtime = build_advance_engine(tmp_path)

    blocked = advance_until_idle(store, runtime, authorize=False)
    assert blocked.executed == []
    assert blocked.stop_reason == "APPROVAL_REQUIRED"
    state = rebuild_state(store.events())
    assert state.tasks[result.task_id]["status"] == "DISCOVERED"

    executed = advance_until_idle(store, runtime, authorize=True)
    assert executed.completed == [result.task_id]
    assert rebuild_state(store.events()).tasks[result.task_id]["status"] == "COMPLETE"


def test_unregistered_capability_remains_non_executable(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    gateway = CanonicalAdapterGateway(store)
    result = gateway.ingest(
        AdapterRequest(
            "aaard",
            "request-remote-shell",
            "shell.exec",
            {"command": "echo should never run"},
        )
    )
    runtime = build_advance_engine(tmp_path)

    report = advance_until_idle(store, runtime, authorize=True)

    assert report.executed == []
    assert report.blocked[result.task_id] == "NO_CAPABILITY"
    assert rebuild_state(store.events()).tasks[result.task_id]["status"] == "DISCOVERED"


def test_adapter_gateway_replay_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "events.sqlite3"
    store = EventStore(path)
    gateway = CanonicalAdapterGateway(store)
    gateway.ingest(AdapterRequest("fras", "claim-7", "system.echo", {"claim_id": "C7"}))

    expected = json.dumps(
        rebuild_state(store.events()).as_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )
    assert store.verify_chain()
    store.close()

    reopened = EventStore(path)
    rebuilt = json.dumps(
        rebuild_state(reopened.events()).as_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )
    assert rebuilt == expected
    assert reopened.verify_chain()
