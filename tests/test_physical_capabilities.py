from pathlib import Path

from centinal26.intent_execution import CapabilityRegistry, IntentExecutionController

from centinal26.event_state import EventStore
from centinal26.physical_capabilities import (
    BoundedLocalExecutor,
    CommandSpec,
    register_physical_capabilities,
)


def test_physical_capability_runs_through_intent_vertical(tmp_path: Path):
    registry = CapabilityRegistry()
    executor = BoundedLocalExecutor({"device.python_version": CommandSpec(("python", "--version"), 10)})
    register_physical_capabilities(registry, executor=executor)
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        result = IntentExecutionController(store, registry).ingest_and_execute(
            text="Proceed", adapter_id="termux-test", external_id="physical-001",
            capability="device.python_version", payload={}, actor="user",
        )
        assert result.completed and result.verified and result.event_chain_valid
    finally:
        store.close()


def test_sha256_capability_is_independently_verified(tmp_path: Path):
    target = tmp_path / "evidence.txt"
    target.write_text("physical-evidence\n", encoding="utf-8")
    registry = CapabilityRegistry()
    register_physical_capabilities(registry)
    store = EventStore(tmp_path / "events.sqlite3")
    try:
        result = IntentExecutionController(store, registry).ingest_and_execute(
            text="Proceed", adapter_id="termux-test", external_id="physical-002",
            capability="device.sha256_file", payload={"path": str(target)},
        )
        assert result.completed and result.verified
    finally:
        store.close()
