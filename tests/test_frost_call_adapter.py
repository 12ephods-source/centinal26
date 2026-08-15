from __future__ import annotations

from pathlib import Path

import pytest

from centinal26.adapter_gateway import AdapterRequestConflict
from centinal26.advance import advance_until_idle, build_advance_engine
from centinal26.event_state import EventStore, rebuild_state
from centinal26.frost_call_adapter import (
    FrostCallProtocolError,
    ingest_frost_call,
    normalize_frost_call,
)
from frost_core.federation import AdapterKind, AdapterStatus, default_federation_catalog


def envelope(
    *,
    request_id: str = "fc-1",
    operation: str = "intent.submit",
    capability: str = "system.echo",
    payload: dict | None = None,
    idempotency_key: str | None = None,
) -> dict:
    return {
        "protocol_version": "frost-call/1.0",
        "request_id": request_id,
        "operation": operation,
        "idempotency_key": idempotency_key or request_id,
        "parameters": {
            "capability": capability,
            "payload": payload or {"message": "hello"},
            "constraints": {"max_runtime_seconds": 30},
            "objective": "frost-call integration test",
            "source": {"transport": "http"},
        },
        "caller": {"type": "test", "id": "test-client"},
        "provenance": {"suite": "test_frost_call_adapter"},
    }


def test_frost_call_normalizes_into_proposal_only_canonical_task(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    result = ingest_frost_call(store, envelope())
    state = rebuild_state(store.events())
    task = state.tasks[result.canonical.task_id]

    assert result.request_id == "fc-1"
    assert result.idempotency_key == "fc-1"
    assert len(result.envelope_sha256) == 64
    assert state.sources[result.canonical.request_id]["adapter_id"] == "frost-call"
    assert state.sources[result.canonical.request_id]["authority"] == "proposal_only"
    assert task["authority"] == "authorization_required"
    assert task["status"] == "DISCOVERED"
    assert task["constraints"]["_frost_call"]["request_id"] == "fc-1"
    assert task["constraints"]["_frost_call"]["caller"]["id"] == "test-client"
    assert task["constraints"]["_frost_call"]["source"]["transport"] == "http"
    assert store.verify_chain()


def test_identical_retry_is_idempotent(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    request = envelope(idempotency_key="stable-key")

    first = ingest_frost_call(store, request)
    second = ingest_frost_call(store, request)

    assert first.canonical.events_appended == 2
    assert second.canonical.events_appended == 0
    assert second.canonical.duplicate is True
    assert second.canonical.task_id == first.canonical.task_id
    assert second.envelope_sha256 == first.envelope_sha256


def test_idempotency_key_reuse_with_changed_content_fails_closed(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    ingest_frost_call(
        store,
        envelope(idempotency_key="stable-key", payload={"message": "first"}),
    )
    count = store.count()

    with pytest.raises(AdapterRequestConflict):
        ingest_frost_call(
            store,
            envelope(idempotency_key="stable-key", payload={"message": "changed"}),
        )

    assert store.count() == count
    assert store.verify_chain()


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("protocol_version", "frost-call/999", "unsupported protocol_version"),
        ("operation", "model.invoke", "unsupported ingress operation"),
    ],
)
def test_invalid_protocol_surface_is_rejected_before_state_change(
    tmp_path: Path, field: str, value: str, match: str
) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    request = envelope()
    request[field] = value

    with pytest.raises(FrostCallProtocolError, match=match):
        ingest_frost_call(store, request)

    assert store.count() == 0


def test_reserved_transport_metadata_cannot_be_spoofed(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    request = envelope()
    request["parameters"]["constraints"]["_frost_call"] = {"authority": "self_granted"}

    with pytest.raises(FrostCallProtocolError, match="reserved"):
        ingest_frost_call(store, request)

    assert store.count() == 0


def test_transport_metadata_cannot_bypass_authorization(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    request = envelope(payload={"message": "proposal", "authorize": True, "grant": "*"})
    result = ingest_frost_call(store, request)
    runtime = build_advance_engine(tmp_path)

    blocked = advance_until_idle(store, runtime, authorize=False)
    assert blocked.executed == []
    assert blocked.stop_reason == "APPROVAL_REQUIRED"
    assert rebuild_state(store.events()).tasks[result.canonical.task_id]["status"] == "DISCOVERED"

    executed = advance_until_idle(store, runtime, authorize=True)
    assert executed.completed == [result.canonical.task_id]
    assert rebuild_state(store.events()).tasks[result.canonical.task_id]["status"] == "COMPLETE"


def test_unregistered_shell_capability_remains_non_executable(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    result = ingest_frost_call(
        store,
        envelope(
            capability="shell.exec",
            payload={"command": "echo should never execute"},
        ),
    )
    runtime = build_advance_engine(tmp_path)

    report = advance_until_idle(store, runtime, authorize=True)

    assert report.executed == []
    assert report.blocked[result.canonical.task_id] == "NO_CAPABILITY"
    assert rebuild_state(store.events()).tasks[result.canonical.task_id]["status"] == "DISCOVERED"


def test_federation_catalog_registers_frost_call_as_descriptive_protocol() -> None:
    descriptor = default_federation_catalog().get("frost-call")

    assert descriptor.kind is AdapterKind.PROTOCOL
    assert descriptor.status is AdapterStatus.DISCOVERED
    assert descriptor.operations == ("intent.submit",)
    assert descriptor.auth_required is True


def test_normalization_is_deterministic() -> None:
    request = envelope()
    left = normalize_frost_call(request)
    right = normalize_frost_call(request)

    assert left == right
    assert left.parameters["payload"] == {"message": "hello"}
