import json
import zipfile
from pathlib import Path

from centinal26.advance import advance_until_idle, build_advance_engine
from centinal26.event_state import EventStore, derive_ready_tasks, rebuild_state
from centinal26.export_evidence import preserve_export
from centinal26.frost_call_adapter import ingest_frost_call


def _export_zip(path: Path) -> Path:
    conversation = {
        "id": "conversation-canonical-flow",
        "title": "Canonical flow",
        "current_node": "assistant",
        "mapping": {
            "user": {
                "id": "user",
                "parent": None,
                "children": ["assistant"],
                "message": {
                    "id": "message-user",
                    "author": {"role": "user"},
                    "create_time": 1.0,
                    "content": {"parts": ["canonical ingress"]},
                },
            },
            "assistant": {
                "id": "assistant",
                "parent": "user",
                "children": [],
                "message": {
                    "id": "message-assistant",
                    "author": {"role": "assistant"},
                    "create_time": 2.0,
                    "content": {"parts": ["verified derived transcript"]},
                },
            },
        },
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("conversations.json", json.dumps([conversation]))
    return path


def test_frost_call_to_authorized_verified_chat_import(tmp_path, monkeypatch):
    evidence_root = tmp_path / "export-evidence"
    archive = _export_zip(tmp_path / "chatgpt-export.zip")
    receipt = preserve_export(
        archive,
        provider="openai",
        root=evidence_root,
        export_id="canonical-flow-export",
    )
    monkeypatch.setenv("CENTINAL26_EXPORT_EVIDENCE_ROOT", str(evidence_root))

    store = EventStore(tmp_path / "events.sqlite3")
    envelope = {
        "protocol_version": "frost-call/1.0",
        "request_id": "canonical-chat-import",
        "operation": "intent.submit",
        "parameters": {
            "capability": "conversation.import_chatgpt_export",
            "payload": {"receipt_id": receipt.receipt_id},
        },
        "caller": {"id": "test-caller", "type": "test"},
        "provenance": {"test": "canonical-chat-import"},
        "idempotency_key": "canonical-chat-import",
    }

    ingested = ingest_frost_call(store, envelope)
    before = rebuild_state(store.events())
    assert before.tasks[ingested.canonical.task_id]["status"] == "DISCOVERED"
    assert ingested.canonical.task_id in derive_ready_tasks(before)

    home = tmp_path / "state"
    runtime = build_advance_engine(home)

    blocked = advance_until_idle(store, runtime, authorize=False, max_tasks=1)
    assert blocked.executed == []
    assert blocked.stop_reason == "APPROVAL_REQUIRED"
    assert blocked.blocked[ingested.canonical.task_id] == "APPROVAL_REQUIRED"

    report = advance_until_idle(store, runtime, authorize=True, max_tasks=1)
    assert report.executed == [ingested.canonical.task_id]
    assert report.completed == [ingested.canonical.task_id]
    assert report.failed == []
    assert report.stop_reason == "COMPLETE"

    state = rebuild_state(store.events())
    task = state.tasks[ingested.canonical.task_id]
    assert task["status"] == "COMPLETE"
    assert store.verify_chain()

    capability_state = runtime.store.get_state("conversation.import_chatgpt_export")
    assert capability_state["verified_runs"] == 1
    assert capability_state["last_receipt_id"] == receipt.receipt_id

    job = runtime.store.db.execute(
        "SELECT state,result,evidence_path FROM jobs WHERE capability=?",
        ("conversation.import_chatgpt_export",),
    ).fetchone()
    assert job["state"] == "verified"
    result = json.loads(job["result"])
    assert result["verified"] is True
    assert runtime.evidence.verify(Path(job["evidence_path"]))
    assert runtime.audit.verify()
