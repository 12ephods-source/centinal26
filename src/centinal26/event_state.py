from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64
EVENT_SCHEMA_VERSION = 1

EVENT_TYPES = frozenset(
    {
        "SOURCE_INGESTED",
        "GOAL_DISCOVERED",
        "TASK_CREATED",
        "DEPENDENCY_ADDED",
        "TASK_READY",
        "TASK_AUTHORIZED",
        "TASK_STARTED",
        "TASK_EXECUTED",
        "VERIFICATION_PASSED",
        "VERIFICATION_FAILED",
        "TASK_COMPLETED",
        "TASK_FAILED",
        "ARTIFACT_CREATED",
        "DECISION_RECORDED",
        "BLOCKER_RECORDED",
    }
)

TASK_EVENT_STATUS = {
    "TASK_READY": "READY",
    "TASK_AUTHORIZED": "AUTHORIZED",
    "TASK_STARTED": "RUNNING",
    "TASK_EXECUTED": "EXECUTED",
    "VERIFICATION_PASSED": "VERIFIED",
    "VERIFICATION_FAILED": "VERIFICATION_FAILED",
    "TASK_COMPLETED": "COMPLETE",
    "TASK_FAILED": "FAILED",
}
TASK_EVENT_ALLOWED_PREVIOUS = {
    "TASK_READY": frozenset({"DISCOVERED"}),
    # Explicit user execution may authorize directly from DISCOVERED; automated
    # execution normally records TASK_READY first.
    "TASK_AUTHORIZED": frozenset({"DISCOVERED", "READY"}),
    "TASK_STARTED": frozenset({"AUTHORIZED"}),
    "TASK_EXECUTED": frozenset({"RUNNING"}),
    "VERIFICATION_PASSED": frozenset({"EXECUTED"}),
    "VERIFICATION_FAILED": frozenset({"EXECUTED"}),
    "TASK_COMPLETED": frozenset({"VERIFIED"}),
    # A task can fail at any non-terminal lifecycle point, including after
    # verification if a later semantic postcondition cannot be committed.
    "TASK_FAILED": frozenset(
        {"DISCOVERED", "READY", "AUTHORIZED", "RUNNING", "EXECUTED", "VERIFIED"}
    ),
}
TERMINAL_TASK_STATES = frozenset({"COMPLETE", "FAILED", "VERIFICATION_FAILED"})


class StateTransitionError(ValueError):
    """Raised when the immutable event history cannot reduce to a valid state."""


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _event_hash(
    *,
    event_id: str,
    ts: str,
    event_type: str,
    entity_id: str | None,
    payload: dict[str, Any],
    prev_hash: str,
) -> str:
    body = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_id": event_id,
        "ts": ts,
        "type": event_type,
        "entity_id": entity_id,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Event:
    seq: int
    event_id: str
    ts: str
    type: str
    entity_id: str | None
    payload: dict[str, Any]
    prev_hash: str
    event_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "event_id": self.event_id,
            "ts": self.ts,
            "type": self.type,
            "entity_id": self.entity_id,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
        }


class EventStore:
    """Append-only SQLite event log with a SHA-256 hash chain."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                ts TEXT NOT NULL,
                type TEXT NOT NULL,
                entity_id TEXT,
                payload_json TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                schema_version INTEGER NOT NULL
            )"""
        )
        self.db.execute(
            """CREATE TRIGGER IF NOT EXISTS events_no_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END"""
        )
        self.db.execute(
            """CREATE TRIGGER IF NOT EXISTS events_no_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END"""
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def append(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        entity_id: str | None = None,
        event_id: str | None = None,
        ts: str | None = None,
    ) -> Event:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {event_type}")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")

        # Round-trip through canonical JSON so the hash and replayed value are identical.
        normalized_payload = json.loads(_canonical_json(payload))
        event_id = event_id or str(uuid.uuid4())
        ts = ts or now_iso()

        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT seq,event_hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            previous_seq = int(row["seq"]) if row else 0
            prev_hash = row["event_hash"] if row else GENESIS_HASH
            digest = _event_hash(
                event_id=event_id,
                ts=ts,
                event_type=event_type,
                entity_id=entity_id,
                payload=normalized_payload,
                prev_hash=prev_hash,
            )
            candidate = Event(
                seq=previous_seq + 1,
                event_id=event_id,
                ts=ts,
                type=event_type,
                entity_id=entity_id,
                payload=normalized_payload,
                prev_hash=prev_hash,
                event_hash=digest,
            )
            # Fail before persistence. An append-only history must never be
            # poisoned by an event whose lifecycle semantics are invalid.
            current_state = rebuild_state(self.events())
            reduce_event(current_state, candidate)

            cursor = self.db.execute(
                """INSERT INTO events (
                    event_id, ts, type, entity_id, payload_json,
                    prev_hash, event_hash, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    ts,
                    event_type,
                    entity_id,
                    _canonical_json(normalized_payload),
                    prev_hash,
                    digest,
                    EVENT_SCHEMA_VERSION,
                ),
            )
            seq = int(cursor.lastrowid)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return Event(
            seq=seq,
            event_id=event_id,
            ts=ts,
            type=event_type,
            entity_id=entity_id,
            payload=normalized_payload,
            prev_hash=prev_hash,
            event_hash=digest,
        )

    def events(self) -> list[Event]:
        rows = self.db.execute("SELECT * FROM events ORDER BY seq").fetchall()
        return [self._row_to_event(row) for row in rows]

    def verify_chain(self) -> bool:
        previous = GENESIS_HASH
        try:
            events = self.events()
            for event in events:
                if event.prev_hash != previous:
                    return False
                if event.type not in EVENT_TYPES:
                    return False
                expected = _event_hash(
                    event_id=event.event_id,
                    ts=event.ts,
                    event_type=event.type,
                    entity_id=event.entity_id,
                    payload=event.payload,
                    prev_hash=event.prev_hash,
                )
                if expected != event.event_hash:
                    return False
                previous = event.event_hash
            # A cryptographically intact history is not valid canonical state
            # if its deterministic lifecycle cannot be replayed.
            rebuild_state(events)
        except (json.JSONDecodeError, StateTransitionError, TypeError, ValueError):
            return False
        return True

    def count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        if int(row["schema_version"]) != EVENT_SCHEMA_VERSION:
            raise StateTransitionError(
                f"unsupported event schema version: {row['schema_version']}"
            )
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise StateTransitionError("event payload is not a JSON object")
        return Event(
            seq=int(row["seq"]),
            event_id=row["event_id"],
            ts=row["ts"],
            type=row["type"],
            entity_id=row["entity_id"],
            payload=payload,
            prev_hash=row["prev_hash"],
            event_hash=row["event_hash"],
        )


@dataclass
class ProjectState:
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    goals: dict[str, dict[str, Any]] = field(default_factory=dict)
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    blockers: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_seq: int = 0
    last_hash: str = GENESIS_HASH

    def as_dict(self) -> dict[str, Any]:
        def ordered(mapping: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
            return {key: mapping[key] for key in sorted(mapping)}

        tasks: dict[str, dict[str, Any]] = {}
        for key in sorted(self.tasks):
            task = dict(self.tasks[key])
            task["dependencies"] = sorted(task.get("dependencies", []))
            tasks[key] = task
        return {
            "sources": ordered(self.sources),
            "goals": ordered(self.goals),
            "tasks": tasks,
            "artifacts": ordered(self.artifacts),
            "decisions": ordered(self.decisions),
            "blockers": ordered(self.blockers),
            "last_seq": self.last_seq,
            "last_hash": self.last_hash,
        }


def _entity_id(event: Event, payload_key: str | None = None) -> str:
    candidate = event.entity_id
    if candidate is None and payload_key is not None:
        value = event.payload.get(payload_key)
        candidate = value if isinstance(value, str) else None
    if not candidate:
        raise StateTransitionError(f"{event.type} requires an entity id")
    return candidate


def _validate_task_transition(task_id: str, current_status: str, event_type: str) -> None:
    allowed = TASK_EVENT_ALLOWED_PREVIOUS[event_type]
    if current_status not in allowed:
        raise StateTransitionError(
            f"illegal task transition for {task_id}: "
            f"{current_status} --{event_type}--> {TASK_EVENT_STATUS[event_type]}"
        )


def reduce_event(state: ProjectState, event: Event) -> ProjectState:
    if event.seq <= state.last_seq:
        raise StateTransitionError("events must be reduced in strictly increasing sequence order")
    if event.prev_hash != state.last_hash:
        raise StateTransitionError("event hash linkage does not match reducer state")

    if event.type == "SOURCE_INGESTED":
        source_id = _entity_id(event, "source_id")
        state.sources[source_id] = dict(event.payload)
    elif event.type == "GOAL_DISCOVERED":
        goal_id = _entity_id(event, "goal_id")
        state.goals[goal_id] = dict(event.payload)
    elif event.type == "TASK_CREATED":
        task_id = _entity_id(event, "task_id")
        if task_id in state.tasks:
            raise StateTransitionError(f"task already exists: {task_id}")
        state.tasks[task_id] = {
            **event.payload,
            "status": "DISCOVERED",
            "dependencies": [],
        }
    elif event.type == "DEPENDENCY_ADDED":
        task_id = event.payload.get("task_id") or event.entity_id
        dependency_id = event.payload.get("depends_on")
        if not isinstance(task_id, str) or not isinstance(dependency_id, str):
            raise StateTransitionError("DEPENDENCY_ADDED requires task_id and depends_on")
        if task_id not in state.tasks:
            raise StateTransitionError(f"unknown task: {task_id}")
        if task_id == dependency_id:
            raise StateTransitionError("task may not depend on itself")
        task_status = str(state.tasks[task_id].get("status"))
        if task_status not in {"DISCOVERED", "READY"}:
            raise StateTransitionError(
                f"dependencies are frozen after authorization: {task_id} is {task_status}"
            )
        dependencies = set(state.tasks[task_id].get("dependencies", []))
        dependencies.add(dependency_id)
        state.tasks[task_id]["dependencies"] = sorted(dependencies)
    elif event.type in TASK_EVENT_STATUS:
        task_id = _entity_id(event, "task_id")
        if task_id not in state.tasks:
            raise StateTransitionError(f"unknown task: {task_id}")
        current_status = str(state.tasks[task_id].get("status"))
        _validate_task_transition(task_id, current_status, event.type)
        state.tasks[task_id]["status"] = TASK_EVENT_STATUS[event.type]
        if event.payload:
            state.tasks[task_id]["last_event"] = dict(event.payload)
    elif event.type == "ARTIFACT_CREATED":
        artifact_id = _entity_id(event, "artifact_id")
        state.artifacts[artifact_id] = dict(event.payload)
    elif event.type == "DECISION_RECORDED":
        decision_id = _entity_id(event, "decision_id")
        state.decisions[decision_id] = dict(event.payload)
    elif event.type == "BLOCKER_RECORDED":
        blocker_id = _entity_id(event, "blocker_id")
        state.blockers[blocker_id] = dict(event.payload)
    else:
        raise StateTransitionError(f"unhandled event type: {event.type}")

    state.last_seq = event.seq
    state.last_hash = event.event_hash
    return state


def rebuild_state(events: Iterable[Event]) -> ProjectState:
    state = ProjectState()
    for event in events:
        reduce_event(state, event)
    return state


def derive_ready_tasks(state: ProjectState) -> list[str]:
    ready: list[str] = []
    for task_id, task in state.tasks.items():
        if task.get("status") in TERMINAL_TASK_STATES | {
            "AUTHORIZED",
            "RUNNING",
            "EXECUTED",
            "VERIFIED",
        }:
            continue
        dependencies = task.get("dependencies", [])
        if all(
            dependency in state.tasks
            and state.tasks[dependency].get("status") == "COMPLETE"
            for dependency in dependencies
        ):
            ready.append(task_id)
    return sorted(ready)


def state_summary(store: EventStore) -> dict[str, Any]:
    chain_valid = store.verify_chain()
    state = rebuild_state(store.events()) if chain_valid else ProjectState()
    return {
        "event_count": store.count(),
        "event_chain_valid": chain_valid,
        "last_seq": state.last_seq if chain_valid else None,
        "last_hash": state.last_hash if chain_valid else None,
        "counts": {
            "sources": len(state.sources),
            "goals": len(state.goals),
            "tasks": len(state.tasks),
            "artifacts": len(state.artifacts),
            "decisions": len(state.decisions),
            "blockers": len(state.blockers),
        },
        "ready_tasks": derive_ready_tasks(state) if chain_valid else [],
    }
