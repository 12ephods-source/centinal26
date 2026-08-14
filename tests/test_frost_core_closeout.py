import asyncio

from frost_core.object_store import CanonicalObjectStore
from frost_core.supervisor import AsyncSupervisor, LeaseQueue, SupervisorResult


def test_object_store_is_immutable_and_preserves_provenance(tmp_path):
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    first = store.put(
        "conversation",
        {"title": "Async Supervisor and Queue"},
        source_type="chatgpt",
        source_ref="automation/async-supervisor-and-queue",
        evidence_class="VERIFIED",
        captured_at=1.0,
    )
    second = store.put(
        "conversation",
        {"title": "Async Supervisor and Queue"},
        source_type="file_library",
        source_ref="CANONICAL_CONVERSATION_BUNDLE.json",
        evidence_class="RECOVERED",
        captured_at=2.0,
    )
    assert first == second
    assert len(store.provenance(first)) == 2
    store.point("conversation/runtime-trunk", first, at=3.0)
    assert store.resolve("conversation/runtime-trunk").object_id == first


def test_supervisor_retries_error_but_preserves_fail(tmp_path):
    queue = LeaseQueue(tmp_path / "queue.sqlite3")
    calls = {"flaky": 0}

    def fail(data):
        return SupervisorResult("FAIL", data)

    def flaky(data):
        calls["flaky"] += 1
        if calls["flaky"] == 1:
            raise RuntimeError("transient")
        return SupervisorResult("PASS", data)

    failed = queue.submit("fail", {"x": 1})
    recovered = queue.submit("flaky", {"x": 2}, max_attempts=2)
    supervisor = AsyncSupervisor(
        queue,
        {"fail": fail, "flaky": flaky},
        max_concurrency=2,
    )
    assert asyncio.run(supervisor.run_until_idle()) == 3
    assert queue.get(failed)["state"] == "FAIL"
    assert queue.get(recovered)["state"] == "PASS"


def test_queue_idempotency(tmp_path):
    queue = LeaseQueue(tmp_path / "queue.sqlite3")
    first = queue.submit("x", {"v": 1}, idempotency_key="same")
    second = queue.submit("x", {"v": 2}, idempotency_key="same")
    assert first == second
