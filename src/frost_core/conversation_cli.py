from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .capability_executor import CapabilityRegistry
from .conversation_loop import ConversationLoop, ConversationStore, LoopPolicy
from .openai_responder import OpenAIResponsesResponder

Json = dict[str, Any]


def _paths() -> tuple[Path, Path]:
    root = Path(
        os.environ.get(
            "FROST_CONVERSATION_HOME",
            Path(os.environ.get("CENTINAL26_HOME", Path.home() / ".local/state/centinal26"))
            / "conversation",
        )
    ).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root / "conversation.sqlite3", root / "capabilities.sqlite3"


def _read_request() -> Json:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("stdin request JSON is required")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    return value


def _emit(value: Json) -> int:
    sys.stdout.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")
    return 0


def _status() -> Json:
    store_path, capabilities_path = _paths()
    store = ConversationStore(store_path)
    capabilities = CapabilityRegistry(capabilities_path)
    try:
        return {
            "status": "ok",
            "conversation": store.status(),
            "capabilities": capabilities.status(),
            "registered_tools": [spec.name for spec in capabilities.list()],
        }
    finally:
        store.close()
        capabilities.close()


def _ingest(request: Json) -> Json:
    conversation_id = str(request.get("conversation_id") or "").strip()
    request_id = str(request.get("request_id") or "").strip()
    content = request.get("content")
    if not conversation_id or not request_id or not isinstance(content, str):
        raise ValueError("conversation.ingest requires conversation_id, request_id, and string content")
    provider = str(request.get("provider") or "openai_responses")
    if provider != "openai_responses":
        raise ValueError(f"unsupported configured responder provider: {provider}")

    store_path, capabilities_path = _paths()
    store = ConversationStore(store_path)
    capabilities = CapabilityRegistry(capabilities_path)
    try:
        configured_instructions = os.environ.get("FROST_CONVERSATION_INSTRUCTIONS", "").strip()
        policy = LoopPolicy(
            max_steps=int(os.environ.get("FROST_CONVERSATION_MAX_STEPS", request.get("max_steps", 12))),
            max_tool_calls=int(
                os.environ.get(
                    "FROST_CONVERSATION_MAX_TOOL_CALLS", request.get("max_tool_calls", 24)
                )
            ),
            max_wall_seconds=int(
                os.environ.get(
                    "FROST_CONVERSATION_MAX_WALL_SECONDS", request.get("max_wall_seconds", 900)
                )
            ),
            instructions=configured_instructions or LoopPolicy().instructions,
        )
        model = os.environ.get("FROST_AI_MODEL") or str(request.get("model") or "gpt-5.6")
        responder = OpenAIResponsesResponder(model=model)
        loop = ConversationLoop(
            store=store,
            capabilities=capabilities,
            responder=responder,
            policy=policy,
        )
        return loop.ingest(
            conversation_id=conversation_id,
            request_id=request_id,
            content=content,
        ).as_json()
    finally:
        store.close()
        capabilities.close()


def _serve() -> int:
    try:
        request = _read_request()
        operation = str(request.get("operation") or "")
        if operation == "conversation.status":
            result = _status()
        elif operation == "conversation.ingest":
            result = _ingest(request)
        else:
            raise ValueError(f"unsupported conversation operation: {operation}")
        return _emit({"ok": True, "operation": operation, "result": result})
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
        return 1


def _register(args: argparse.Namespace) -> int:
    _, capabilities_path = _paths()
    registry = CapabilityRegistry(capabilities_path)
    try:
        spec = registry.register(
            name=args.name,
            script_path=Path(args.script),
            description=args.description,
            timeout_seconds=args.timeout,
            max_args=args.max_args,
            max_arg_length=args.max_arg_length,
            max_output_bytes=args.max_output_bytes,
            allow_network=args.allow_network,
        )
        return _emit(
            {
                "ok": True,
                "registered": {
                    "name": spec.name,
                    "script_path": spec.script_path,
                    "script_sha256": spec.script_sha256,
                    "allow_network": spec.allow_network,
                },
            }
        )
    finally:
        registry.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="centinal26-conversation")
    sub = parser.add_subparsers(dest="command")
    register = sub.add_parser("register", help="register a local hash-pinned capability")
    register.add_argument("--name", required=True)
    register.add_argument("--script", required=True)
    register.add_argument("--description", required=True)
    register.add_argument("--timeout", type=int, default=120)
    register.add_argument("--max-args", type=int, default=12)
    register.add_argument("--max-arg-length", type=int, default=512)
    register.add_argument("--max-output-bytes", type=int, default=200_000)
    register.add_argument("--allow-network", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "register":
        return _register(args)
    return _serve()


if __name__ == "__main__":
    raise SystemExit(main())
