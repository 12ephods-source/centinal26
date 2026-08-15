from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .event_state import EventStore, ProjectState, rebuild_state

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
_TEXT_PATTERN = re.compile(
    r"^(GOAL|TASK|DECISION|BLOCKER|ARTIFACT)(?:\s*\[([^\]]+)\])?\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
_DEPENDS_PATTERN = re.compile(
    r"^DEPENDS\s*:\s*([^\s]+)\s*->\s*([^\s]+)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PendingRecord:
    kind: str
    external_id: str
    text: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestResult:
    source_id: str
    sha256: str
    duplicate: bool
    events_appended: int
    extracted: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "sha256": self.sha256,
            "duplicate": self.duplicate,
            "events_appended": self.events_appended,
            "extracted": dict(sorted(self.extracted.items())),
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_id_for(data: bytes) -> str:
    return f"source:{sha256_bytes(data)}"


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return token[:80] or "item"


def _entity_id(kind: str, digest: str, external_id: str) -> str:
    return f"{kind}:{digest[:16]}:{_safe_token(external_id)}"


def _record_from_item(kind: str, item: Any, index: int) -> PendingRecord:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            raise ValueError(f"empty {kind} entry at index {index}")
        return PendingRecord(kind, str(index + 1), text)
    if not isinstance(item, dict):
        raise TypeError(f"{kind} entry {index} must be a string or object")
    external_id = str(item.get("id", index + 1))
    text_value = (
        item.get("text")
        or item.get("objective")
        or item.get("title")
        or item.get("description")
    )
    if not isinstance(text_value, str) or not text_value.strip():
        raise ValueError(f"{kind} entry {index} has no text/objective/title/description")
    payload = {key: value for key, value in item.items() if key != "id"}
    return PendingRecord(kind, external_id, text_value.strip(), payload)


def _extract_json(data: Any) -> tuple[list[PendingRecord], list[tuple[str, str]]]:
    if not isinstance(data, dict):
        raise TypeError("structured ingestion requires a top-level JSON object")

    records: list[PendingRecord] = []
    dependencies: list[tuple[str, str]] = []
    singular = {
        "goals": "goal",
        "tasks": "task",
        "decisions": "decision",
        "blockers": "blocker",
        "artifacts": "artifact",
    }
    for collection, kind in singular.items():
        raw = data.get(collection, [])
        if raw is None:
            continue
        if not isinstance(raw, list):
            raise TypeError(f"{collection} must be an array")
        for index, item in enumerate(raw):
            record = _record_from_item(kind, item, index)
            records.append(record)
            if kind == "task" and isinstance(item, dict):
                depends_on = item.get("depends_on", [])
                if isinstance(depends_on, str):
                    depends_on = [depends_on]
                if not isinstance(depends_on, list) or not all(
                    isinstance(value, str) for value in depends_on
                ):
                    raise TypeError("task depends_on must be a string or array of strings")
                dependencies.extend((record.external_id, value) for value in depends_on)

    raw_dependencies = data.get("dependencies", [])
    if raw_dependencies is not None:
        if not isinstance(raw_dependencies, list):
            raise TypeError("dependencies must be an array")
        for index, item in enumerate(raw_dependencies):
            if not isinstance(item, dict):
                raise TypeError(f"dependency entry {index} must be an object")
            task = item.get("task_id") or item.get("task")
            depends_on = item.get("depends_on")
            if not isinstance(task, str) or not isinstance(depends_on, str):
                raise TypeError("dependency requires task_id/task and depends_on strings")
            dependencies.append((task, depends_on))

    return records, dependencies


def _extract_text(text: str) -> tuple[list[PendingRecord], list[tuple[str, str]]]:
    records: list[PendingRecord] = []
    dependencies: list[tuple[str, str]] = []
    counters: dict[str, int] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        dependency = _DEPENDS_PATTERN.match(line)
        if dependency:
            dependencies.append((dependency.group(1), dependency.group(2)))
            continue
        match = _TEXT_PATTERN.match(line)
        if not match:
            continue
        kind = match.group(1).lower()
        counters[kind] = counters.get(kind, 0) + 1
        external_id = match.group(2) or f"line-{line_number}-{counters[kind]}"
        records.append(PendingRecord(kind, external_id, match.group(3).strip()))
    return records, dependencies


def _extract(content: bytes, suffix: str) -> tuple[list[PendingRecord], list[tuple[str, str]], str]:
    text = content.decode("utf-8")
    if suffix.lower() == ".json":
        records, dependencies = _extract_json(json.loads(text))
        return records, dependencies, "application/json"
    records, dependencies = _extract_text(text)
    return records, dependencies, "text/plain"


def _validate_plan(
    records: list[PendingRecord], dependencies: list[tuple[str, str]], digest: str
) -> dict[str, str]:
    seen: set[tuple[str, str]] = set()
    task_ids: dict[str, str] = {}
    for record in records:
        key = (record.kind, record.external_id)
        if key in seen:
            raise ValueError(f"duplicate {record.kind} id: {record.external_id}")
        seen.add(key)
        if record.kind == "task":
            task_ids[record.external_id] = _entity_id("task", digest, record.external_id)
    for task_external, _dependency_external in dependencies:
        if task_external not in task_ids:
            raise ValueError(f"dependency references unknown task id: {task_external}")
    return task_ids


def _existing_state(store: EventStore) -> ProjectState:
    if not store.verify_chain():
        raise ValueError("refusing ingestion because the event chain is invalid")
    return rebuild_state(store.events())


def ingest_bytes(
    store: EventStore,
    content: bytes,
    *,
    name: str = "input.txt",
    path: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> IngestResult:
    if len(content) > max_bytes:
        raise ValueError(f"source exceeds max_bytes={max_bytes}")
    digest = sha256_bytes(content)
    source_id = f"source:{digest}"
    state = _existing_state(store)
    if source_id in state.sources:
        return IngestResult(source_id, digest, True, 0, {})

    suffix = Path(name).suffix
    records, dependencies, media_type = _extract(content, suffix)
    task_ids = _validate_plan(records, dependencies, digest)

    event_type = {
        "goal": "GOAL_DISCOVERED",
        "task": "TASK_CREATED",
        "decision": "DECISION_RECORDED",
        "blocker": "BLOCKER_RECORDED",
        "artifact": "ARTIFACT_CREATED",
    }
    id_key = {
        "goal": "goal_id",
        "task": "task_id",
        "decision": "decision_id",
        "blocker": "blocker_id",
        "artifact": "artifact_id",
    }

    start_count = store.count()
    store.append(
        "SOURCE_INGESTED",
        {
            "source_id": source_id,
            "sha256": digest,
            "bytes": len(content),
            "name": name,
            "path": path,
            "media_type": media_type,
        },
        entity_id=source_id,
    )

    counts: dict[str, int] = {}
    for record in records:
        internal_id = _entity_id(record.kind, digest, record.external_id)
        payload = {
            id_key[record.kind]: internal_id,
            "source_id": source_id,
            "external_id": record.external_id,
            "text": record.text,
            **record.payload,
        }
        if record.kind == "task":
            payload.setdefault("objective", record.text)
            payload.pop("depends_on", None)
        store.append(event_type[record.kind], payload, entity_id=internal_id)
        counts[record.kind] = counts.get(record.kind, 0) + 1

    for task_external, dependency_external in dependencies:
        task_id = task_ids[task_external]
        dependency_id = task_ids.get(dependency_external)
        if dependency_id is None:
            dependency_id = _entity_id("task", digest, dependency_external)
        store.append(
            "DEPENDENCY_ADDED",
            {
                "task_id": task_id,
                "depends_on": dependency_id,
                "source_id": source_id,
                "external_task_id": task_external,
                "external_dependency_id": dependency_external,
            },
            entity_id=task_id,
        )
        counts["dependency"] = counts.get("dependency", 0) + 1

    return IngestResult(
        source_id=source_id,
        sha256=digest,
        duplicate=False,
        events_appended=store.count() - start_count,
        extracted=counts,
    )


def ingest_path(
    store: EventStore,
    path: Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> IngestResult:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return ingest_bytes(
        store,
        resolved.read_bytes(),
        name=resolved.name,
        path=str(resolved),
        max_bytes=max_bytes,
    )


def discover_paths(paths: list[Path], *, recursive: bool = False) -> list[Path]:
    discovered: set[Path] = set()
    for raw in paths:
        path = raw.expanduser()
        if path.is_file():
            discovered.add(path.resolve())
            continue
        if path.is_dir() and recursive:
            for candidate in path.rglob("*"):
                if candidate.is_file():
                    discovered.add(candidate.resolve())
            continue
        if path.is_dir():
            raise IsADirectoryError(f"{path}: use --recursive to ingest a directory")
        raise FileNotFoundError(path)
    return sorted(discovered, key=str)
