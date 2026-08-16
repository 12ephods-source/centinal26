import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from centinal26.chat_bridge import (
    ChatBridgeError,
    import_verified_chatgpt_export,
    register_chat_bridge_capabilities,
    verify_chatgpt_import,
)
from centinal26.core import AuditLog, Grant
from centinal26.export_evidence import preserve_export
from centinal26.pipeline import AutomatedEngine, EvidenceStore, Intent, RuntimeStore


def _message(message_id: str, role: str, text: str, created: float) -> dict:
    return {
        "id": message_id,
        "author": {"role": role},
        "create_time": created,
        "content": {"parts": [text]},
    }


def _export_zip(path: Path) -> Path:
    conversation = {
        "id": "conversation-1",
        "title": "Branch test",
        "current_node": "good",
        "mapping": {
            "root": {
                "id": "root",
                "parent": None,
                "children": ["good", "alternate"],
                "message": _message("m-root", "user", "selected user turn", 1.0),
            },
            "good": {
                "id": "good",
                "parent": "root",
                "children": [],
                "message": _message("m-good", "assistant", "selected answer", 2.0),
            },
            "alternate": {
                "id": "alternate",
                "parent": "root",
                "children": [],
                "message": _message("m-alt", "assistant", "alternate answer", 1.5),
            },
        },
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("nested/conversations.json", json.dumps([conversation]))
    return path


def _grant(capability: str) -> Grant:
    return Grant(
        grant_id="chat-import-test",
        capability=capability,
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )


def _preserved(tmp_path: Path):
    archive = _export_zip(tmp_path / "export.zip")
    root = tmp_path / "export-evidence"
    receipt = preserve_export(
        archive,
        provider="openai",
        root=root,
        export_id="export-1",
    )
    return root, receipt


def test_verified_import_follows_selected_branch_and_binds_receipt(tmp_path):
    evidence_root, receipt = _preserved(tmp_path)
    home = tmp_path / "home"
    output = import_verified_chatgpt_export(
        {"receipt_id": receipt.receipt_id},
        home=home,
        evidence_root=evidence_root,
    )

    assert verify_chatgpt_import(
        {"receipt_id": receipt.receipt_id},
        output,
        home=home,
        evidence_root=evidence_root,
    )
    manifest = json.loads(Path(output["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["source_receipt_id"] == receipt.receipt_id
    assert manifest["source_sha256"] == receipt.sha256
    assert manifest["conversation_count"] == 1
    assert manifest["message_count"] == 2

    transcript = Path(output["destination"]) / manifest["conversations"][0]["relative_path"]
    text = transcript.read_text(encoding="utf-8")
    assert "selected user turn" in text
    assert "selected answer" in text
    assert "alternate answer" not in text


def test_independent_verifier_detects_derived_transcript_tamper(tmp_path):
    evidence_root, receipt = _preserved(tmp_path)
    home = tmp_path / "home"
    payload = {"receipt_id": receipt.receipt_id}
    output = import_verified_chatgpt_export(
        payload,
        home=home,
        evidence_root=evidence_root,
    )
    manifest = json.loads(Path(output["manifest_path"]).read_text(encoding="utf-8"))
    transcript = Path(output["destination"]) / manifest["conversations"][0]["relative_path"]
    transcript.write_text("tampered\n", encoding="utf-8")
    assert not verify_chatgpt_import(
        payload,
        output,
        home=home,
        evidence_root=evidence_root,
    )


def test_payload_cannot_select_arbitrary_source_or_destination(tmp_path):
    evidence_root, receipt = _preserved(tmp_path)
    with pytest.raises(ChatBridgeError):
        import_verified_chatgpt_export(
            {
                "receipt_id": receipt.receipt_id,
                "destination": "/tmp/remote-selected-path",
            },
            home=tmp_path / "home",
            evidence_root=evidence_root,
        )


def test_capability_executes_through_automated_engine_with_evidence_gate(tmp_path):
    evidence_root, receipt = _preserved(tmp_path)
    home = tmp_path / "home"
    runtime = AutomatedEngine(
        RuntimeStore(tmp_path / "runtime.sqlite3"),
        AuditLog(tmp_path / "audit.jsonl"),
        EvidenceStore(tmp_path / "execution-evidence"),
    )
    register_chat_bridge_capabilities(runtime, home, evidence_root=evidence_root)
    capability = "conversation.import_chatgpt_export"
    intent = Intent(capability, {"receipt_id": receipt.receipt_id})
    job_id = runtime.submit(intent, _grant(capability), idempotency_key="chat-import-1")

    assert runtime.run_once() == job_id
    row = runtime.store.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert row["state"] == "verified"
    result = json.loads(row["result"])
    assert result["verified"] is True
    assert runtime.evidence.verify(Path(row["evidence_path"]))
    state = runtime.store.get_state(capability)
    assert state["verified_runs"] == 1
    assert state["last_receipt_id"] == receipt.receipt_id
    assert runtime.audit.verify()
