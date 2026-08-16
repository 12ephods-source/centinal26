from __future__ import annotations

import json
from pathlib import Path

import pytest

from frost_core.capability_executor import CapabilityRegistry
from frost_core.conversation_cli import _status
from frost_core.conversation_loop import (
    ConversationLoop,
    ConversationStore,
    LoopPolicy,
    ResponderStep,
    ToolCall,
)
from frost_core.openai_responder import OpenAIResponsesResponder


class FakeResponder:
    provider_id = "fake"
    model = "fake-1"

    def __init__(self):
        self.calls = 0
        self.inputs = []

    def respond(self, *, input_items, previous_response_id, tools, instructions):
        self.calls += 1
        self.inputs.append((input_items, previous_response_id, tools, instructions))
        if self.calls == 1:
            assert previous_response_id is None
            assert tools[0]["name"].startswith("frost_termux_system_status_")
            return ResponderStep(
                response_id="resp-1",
                tool_calls=(
                    ToolCall(
                        call_id="call-1",
                        name=tools[0]["name"],
                        arguments={"args": []},
                    ),
                ),
            )
        assert previous_response_id == "resp-1"
        assert input_items[0]["type"] == "function_call_output"
        output = json.loads(input_items[0]["output"])
        assert output["stdout"].strip() == "DEVICE_OK"
        return ResponderStep(response_id="resp-2", text="Device reports DEVICE_OK.")


def make_script(path: Path, counter: Path) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        f"n=$(cat '{counter}' 2>/dev/null || echo 0)\n"
        f"echo $((n+1)) > '{counter}'\n"
        "printf 'DEVICE_OK\\n'\n",
        encoding="utf-8",
    )
    path.chmod(0o700)
    return path


def test_tool_feedback_loop_and_cached_ingress(tmp_path: Path):
    counter = tmp_path / "counter"
    script = make_script(tmp_path / "status.sh", counter)
    registry = CapabilityRegistry(tmp_path / "cap.sqlite3")
    store = ConversationStore(tmp_path / "conversation.sqlite3")
    try:
        registry.register(
            name="termux.system_status",
            script_path=script,
            description="Return bounded device status",
            max_args=0,
        )
        responder = FakeResponder()
        loop = ConversationLoop(
            store=store,
            capabilities=registry,
            responder=responder,
            policy=LoopPolicy(max_steps=4, max_tool_calls=2, max_wall_seconds=30),
        )
        result = loop.ingest(
            conversation_id="conv-1", request_id="req-1", content="Check the device."
        )
        assert result.status == "completed"
        assert result.response == "Device reports DEVICE_OK."
        assert result.steps == 2
        assert result.tool_calls == 1
        assert counter.read_text().strip() == "1"

        cached = loop.ingest(
            conversation_id="conv-1", request_id="req-1", content="Check the device."
        )
        assert cached.cached is True
        assert cached.response == result.response
        assert responder.calls == 2
        assert counter.read_text().strip() == "1"
    finally:
        store.close()
        registry.close()


def test_capability_call_id_is_exactly_once_locally(tmp_path: Path):
    counter = tmp_path / "counter"
    script = make_script(tmp_path / "status.sh", counter)
    registry = CapabilityRegistry(tmp_path / "cap.sqlite3")
    try:
        registry.register(
            name="termux.system_status",
            script_path=script,
            description="Return bounded device status",
            max_args=0,
        )
        first = registry.execute(call_id="same-call", name="termux.system_status", args=[])
        second = registry.execute(call_id="same-call", name="termux.system_status", args=[])
        assert first == second
        assert counter.read_text().strip() == "1"
        with pytest.raises(RuntimeError):
            registry.execute(call_id="same-call", name="termux.system_status", args=["different"])
    finally:
        registry.close()


def test_hash_drift_is_denied(tmp_path: Path):
    counter = tmp_path / "counter"
    script = make_script(tmp_path / "status.sh", counter)
    registry = CapabilityRegistry(tmp_path / "cap.sqlite3")
    try:
        registry.register(
            name="termux.system_status",
            script_path=script,
            description="Return bounded device status",
            max_args=0,
        )
        script.write_text("#!/bin/sh\necho CHANGED\n", encoding="utf-8")
        script.chmod(0o700)
        with pytest.raises(PermissionError, match="hash changed"):
            registry.execute(call_id="drift", name="termux.system_status", args=[])
    finally:
        registry.close()


def test_openai_response_parser_handles_tool_and_text():
    step = OpenAIResponsesResponder._parse(
        {
            "id": "resp_123",
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call_123",
                    "name": "frost_termux_system_status_12345678",
                    "arguments": '{"args":[]}',
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "done"}],
                },
            ],
        }
    )
    assert step.response_id == "resp_123"
    assert step.text == "done"
    assert step.tool_calls[0].call_id == "call_123"
    assert step.tool_calls[0].arguments == {"args": []}


def test_status_reports_registered_tools(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FROST_CONVERSATION_HOME", str(tmp_path))
    script = tmp_path / "status.sh"
    script.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    script.chmod(0o700)
    registry = CapabilityRegistry(tmp_path / "capabilities.sqlite3")
    try:
        registry.register(name="test.status", script_path=script, description="test", max_args=0)
    finally:
        registry.close()
    result = _status()
    assert result["status"] == "ok"
    assert result["registered_tools"] == ["test.status"]
    assert result["capabilities"]["enabled_capabilities"] == 1
