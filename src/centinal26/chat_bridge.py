from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .export_evidence import DEFAULT_ROOT, verify_receipt
from .pipeline import AutomatedEngine, CapabilitySpec

Json = dict[str, Any]
_RECEIPT_ID = re.compile(r"^[0-9a-f]{64}$")


class ChatBridgeError(RuntimeError):
    """A ChatGPT export bridge operation failed."""


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _extract_text_from_message(message: Json) -> str:
    content = message.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    output: list[str] = []
    for part in parts:
        if isinstance(part, str):
            output.append(part)
        elif isinstance(part, dict):
            value = part.get("text")
            if not isinstance(value, str):
                value = part.get("content")
            if isinstance(value, str):
                output.append(value)
    return "\n".join(value for value in output if value).strip()


def _iter_chatgpt_conversations(data: Any) -> Iterator[Json]:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("mapping"), dict):
                yield item
        return
    if isinstance(data, dict):
        conversations = data.get("conversations")
        if isinstance(conversations, list):
            yield from _iter_chatgpt_conversations(conversations)


def _node_path_to_current(conversation: Json) -> list[Json]:
    mapping = conversation.get("mapping")
    current_node = conversation.get("current_node")
    if not isinstance(mapping, dict) or not isinstance(current_node, str):
        return []
    path: list[Json] = []
    seen: set[str] = set()
    node_id: str | None = current_node
    while isinstance(node_id, str) and node_id and node_id not in seen:
        seen.add(node_id)
        node = mapping.get(node_id)
        if not isinstance(node, dict):
            return []
        path.append(node)
        parent = node.get("parent")
        node_id = parent if isinstance(parent, str) and parent else None
    if node_id in seen:
        return []
    path.reverse()
    return path


def _message_sort_key(item: Json) -> tuple[int, float, str]:
    created = item.get("create_time")
    if isinstance(created, (int, float)):
        return (0, float(created), str(item.get("message_id") or ""))
    return (1, 0.0, str(item.get("message_id") or ""))


def _messages_from_conversation(conversation: Json) -> list[Json]:
    mapping = conversation.get("mapping")
    if not isinstance(mapping, dict):
        return []
    selected_nodes = _node_path_to_current(conversation)
    preserve_graph_order = bool(selected_nodes)
    nodes: Iterable[Json]
    if preserve_graph_order:
        nodes = selected_nodes
    else:
        nodes = (node for node in mapping.values() if isinstance(node, dict))
    messages: list[Json] = []
    for node in nodes:
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        text = _extract_text_from_message(message)
        if not text:
            continue
        author = message.get("author")
        role = str(author.get("role") or "unknown") if isinstance(author, dict) else "unknown"
        messages.append(
            {
                "role": role,
                "text": text,
                "create_time": message.get("create_time"),
                "message_id": message.get("id"),
            }
        )
    if not preserve_graph_order:
        messages.sort(key=_message_sort_key)
    return messages


def _safe_filename_component(title: str, *, limit: int = 80) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in title).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe[:limit] or "conversation"


def _display_title(title: str) -> str:
    return " ".join(title.split()) or "Untitled conversation"


def _load_export_json(export_path: Path) -> Any:
    try:
        if export_path.suffix.lower() == ".zip" or zipfile.is_zipfile(export_path):
            with zipfile.ZipFile(export_path) as archive:
                candidates = sorted(
                    (
                        info
                        for info in archive.infolist()
                        if not info.is_dir()
                        and Path(info.filename).name.lower() == "conversations.json"
                    ),
                    key=lambda info: (len(Path(info.filename).parts), info.filename),
                )
                if not candidates:
                    raise ChatBridgeError("The ZIP does not contain conversations.json.")
                with (
                    archive.open(candidates[0], "r") as raw,
                    io.TextIOWrapper(raw, encoding="utf-8-sig") as stream,
                ):
                    return json.load(stream)
        with export_path.open("r", encoding="utf-8-sig") as stream:
            return json.load(stream)
    except ChatBridgeError:
        raise
    except FileNotFoundError as exc:
        raise ChatBridgeError(f"Export file does not exist: {export_path}") from exc
    except PermissionError as exc:
        raise ChatBridgeError(f"Export file is not readable: {export_path}") from exc
    except zipfile.BadZipFile as exc:
        raise ChatBridgeError(f"Invalid ZIP archive: {export_path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ChatBridgeError(f"Export does not contain valid UTF-8 JSON: {export_path}") from exc
    except OSError as exc:
        raise ChatBridgeError(f"Could not read export {export_path}: {exc}") from exc


def import_chatgpt_export(
    export_path: Path,
    destination: Path,
    *,
    source_receipt_id: str | None = None,
) -> Json:
    export_path = export_path.expanduser().resolve()
    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    data = _load_export_json(export_path)
    index: list[Json] = []
    total_messages = 0
    for number, conversation in enumerate(_iter_chatgpt_conversations(data), start=1):
        raw_title = str(conversation.get("title") or f"Conversation {number}").strip()
        title = raw_title or f"Conversation {number}"
        conversation_id = str(
            conversation.get("id") or conversation.get("conversation_id") or number
        )
        messages = _messages_from_conversation(conversation)
        total_messages += len(messages)
        md_path = destination / f"{number:05d}-{_safe_filename_component(title)}.md"
        lines = [
            f"# {_display_title(title)}",
            "",
            f"Conversation ID: `{conversation_id}`",
            "",
        ]
        for item in messages:
            lines.extend([f"## {item['role'].title()}", "", item["text"], ""])
        markdown = "\n".join(lines).rstrip() + "\n"
        _atomic_write_text(md_path, markdown)
        index.append(
            {
                "conversation_id": conversation_id,
                "title": title,
                "messages": len(messages),
                "relative_path": md_path.name,
                "sha256": _sha256_text(markdown),
            }
        )
    manifest: Json = {
        "schema_version": 1,
        "imported_at": _utc_now_iso(),
        "source_receipt_id": source_receipt_id,
        "source_size_bytes": export_path.stat().st_size,
        "source_sha256": _sha256_file(export_path),
        "conversation_count": len(index),
        "message_count": total_messages,
        "conversations": index,
    }
    manifest_path = destination / "chatgpt-import-manifest.json"
    _atomic_write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    return manifest


def _required_receipt_id(payload: Json) -> str:
    if set(payload) != {"receipt_id"}:
        raise ChatBridgeError("payload must contain exactly one field: receipt_id")
    receipt_id = payload.get("receipt_id")
    if not isinstance(receipt_id, str) or not _RECEIPT_ID.fullmatch(receipt_id):
        raise ChatBridgeError("receipt_id must be a lowercase 64-character SHA-256 identifier")
    return receipt_id


def _import_destination(home: Path, receipt_id: str) -> Path:
    return home.expanduser().resolve() / "chat-imports" / receipt_id


def import_verified_chatgpt_export(
    payload: Json,
    *,
    home: Path,
    evidence_root: Path = DEFAULT_ROOT,
) -> Json:
    receipt_id = _required_receipt_id(payload)
    verified = verify_receipt(evidence_root, receipt_id)
    destination = _import_destination(home, receipt_id)
    manifest = import_chatgpt_export(
        Path(verified.object_path),
        destination,
        source_receipt_id=receipt_id,
    )
    manifest_path = destination / "chatgpt-import-manifest.json"
    return {
        "receipt_id": receipt_id,
        "source_sha256": verified.sha256,
        "source_size_bytes": verified.size,
        "destination": str(destination),
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256_file(manifest_path),
        "conversation_count": manifest["conversation_count"],
        "message_count": manifest["message_count"],
    }


def verify_chatgpt_import(
    payload: Json,
    output: Json,
    *,
    home: Path,
    evidence_root: Path = DEFAULT_ROOT,
) -> bool:
    try:
        receipt_id = _required_receipt_id(payload)
        verified = verify_receipt(evidence_root, receipt_id)
        destination = _import_destination(home, receipt_id)
        manifest_path = destination / "chatgpt-import-manifest.json"
        if output.get("receipt_id") != receipt_id:
            return False
        if output.get("source_sha256") != verified.sha256:
            return False
        if output.get("source_size_bytes") != verified.size:
            return False
        if Path(str(output.get("destination", ""))).resolve() != destination:
            return False
        if Path(str(output.get("manifest_path", ""))).resolve() != manifest_path:
            return False
        if not manifest_path.is_file():
            return False
        if output.get("manifest_sha256") != _sha256_file(manifest_path):
            return False
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        conversations = manifest.get("conversations")
        if not isinstance(conversations, list):
            return False
        if manifest.get("schema_version") != 1:
            return False
        if manifest.get("source_receipt_id") != receipt_id:
            return False
        if manifest.get("source_sha256") != verified.sha256:
            return False
        if manifest.get("source_size_bytes") != verified.size:
            return False
        if manifest.get("conversation_count") != len(conversations):
            return False
        if output.get("conversation_count") != len(conversations):
            return False
        total_messages = 0
        seen_paths: set[str] = set()
        for item in conversations:
            if not isinstance(item, dict):
                return False
            relative_path = item.get("relative_path")
            if not isinstance(relative_path, str) or not relative_path:
                return False
            relative = Path(relative_path)
            if relative.is_absolute() or len(relative.parts) != 1 or relative_path in seen_paths:
                return False
            seen_paths.add(relative_path)
            transcript = (destination / relative).resolve()
            try:
                transcript.relative_to(destination)
            except ValueError:
                return False
            if not transcript.is_file() or _sha256_file(transcript) != item.get("sha256"):
                return False
            messages = item.get("messages")
            if not isinstance(messages, int) or messages < 0:
                return False
            total_messages += messages
        return (
            manifest.get("message_count") == total_messages
            and output.get("message_count") == total_messages
        )
    except (ChatBridgeError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        return False


def chat_import_reducer(current: Json, output: Json) -> Json:
    return {
        "verified_runs": int(current.get("verified_runs", 0)) + 1,
        "last_receipt_id": output["receipt_id"],
        "last_source_sha256": output["source_sha256"],
        "last_manifest_sha256": output["manifest_sha256"],
        "last_conversation_count": output["conversation_count"],
        "last_message_count": output["message_count"],
    }


def chat_export_import_capability(
    home: Path,
    *,
    evidence_root: Path | None = None,
) -> CapabilitySpec:
    resolved_home = home.expanduser().resolve()
    configured_root = evidence_root
    if configured_root is None:
        configured_root = Path(os.environ.get("CENTINAL26_EXPORT_EVIDENCE_ROOT", DEFAULT_ROOT))
    resolved_evidence_root = configured_root.expanduser().resolve()

    def execute(payload: Json) -> Json:
        return import_verified_chatgpt_export(
            payload,
            home=resolved_home,
            evidence_root=resolved_evidence_root,
        )

    def verify(payload: Json, output: Json) -> bool:
        return verify_chatgpt_import(
            payload,
            output,
            home=resolved_home,
            evidence_root=resolved_evidence_root,
        )

    return CapabilitySpec(
        name="conversation.import_chatgpt_export",
        executor=execute,
        verifier=verify,
        reducer=chat_import_reducer,
        timeout_seconds=120.0,
        max_attempts=2,
        verifier_independent=True,
    )


def register_chat_bridge_capabilities(
    engine: AutomatedEngine,
    home: Path,
    *,
    evidence_root: Path | None = None,
) -> None:
    engine.register(chat_export_import_capability(home, evidence_root=evidence_root))
