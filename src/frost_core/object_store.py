from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class StoredObject:
    object_id: str
    kind: str
    payload: Any
    created_at: float


class CanonicalObjectStore:
    """Immutable content-addressed objects plus append-only provenance.

    Mutable concepts such as ``release/current`` are aliases. Alias updates are
    recorded in history, so changing the current pointer never rewrites an
    existing object.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS objects (
                    object_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    body_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_objects_kind ON objects(kind);
                CREATE TABLE IF NOT EXISTS provenance (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    object_id TEXT NOT NULL REFERENCES objects(object_id),
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    evidence_class TEXT NOT NULL,
                    captured_at REAL NOT NULL,
                    UNIQUE(object_id, source_type, source_ref, evidence_class)
                );
                CREATE TABLE IF NOT EXISTS links (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT NOT NULL REFERENCES objects(object_id),
                    relation TEXT NOT NULL,
                    child_id TEXT NOT NULL REFERENCES objects(object_id),
                    created_at REAL NOT NULL,
                    UNIQUE(parent_id, relation, child_id)
                );
                CREATE TABLE IF NOT EXISTS aliases (
                    alias TEXT PRIMARY KEY,
                    object_id TEXT NOT NULL REFERENCES objects(object_id),
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alias_history (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT NOT NULL,
                    object_id TEXT NOT NULL REFERENCES objects(object_id),
                    updated_at REAL NOT NULL
                );
                """
            )

    def put(
        self,
        kind: str,
        payload: Any,
        *,
        source_type: str = "generated",
        source_ref: str = "",
        evidence_class: str = "UNCLASSIFIED",
        captured_at: float | None = None,
    ) -> str:
        kind = str(kind).strip()
        if not kind:
            raise ValueError("kind may not be empty")
        envelope = {
            "schema": self.SCHEMA_VERSION,
            "kind": kind,
            "payload": payload,
        }
        object_id = _digest(envelope)
        body_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        now = time.time() if captured_at is None else float(captured_at)
        with self._connect() as db:
            db.execute(
                """INSERT OR IGNORE INTO objects
                   (object_id,kind,body_json,created_at) VALUES (?,?,?,?)""",
                (object_id, kind, body_json, now),
            )
            db.execute(
                """INSERT OR IGNORE INTO provenance
                   (object_id,source_type,source_ref,evidence_class,captured_at)
                   VALUES (?,?,?,?,?)""",
                (object_id, source_type, source_ref, evidence_class, now),
            )
        return object_id

    def get(self, object_id: str) -> StoredObject:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM objects WHERE object_id=?",
                (object_id,),
            ).fetchone()
        if row is None:
            raise KeyError(object_id)
        body = json.loads(row["body_json"])
        return StoredObject(
            object_id=row["object_id"],
            kind=row["kind"],
            payload=body["payload"],
            created_at=float(row["created_at"]),
        )

    def link(self, parent_id: str, relation: str, child_id: str) -> None:
        relation = str(relation).strip()
        if not relation:
            raise ValueError("relation may not be empty")
        with self._connect() as db:
            for object_id in (parent_id, child_id):
                found = db.execute(
                    "SELECT 1 FROM objects WHERE object_id=?",
                    (object_id,),
                ).fetchone()
                if found is None:
                    raise KeyError(object_id)
            db.execute(
                """INSERT OR IGNORE INTO links
                   (parent_id,relation,child_id,created_at) VALUES (?,?,?,?)""",
                (parent_id, relation, child_id, time.time()),
            )

    def point(self, alias: str, object_id: str, *, at: float | None = None) -> None:
        alias = str(alias).strip()
        if not alias:
            raise ValueError("alias may not be empty")
        now = time.time() if at is None else float(at)
        with self._connect() as db:
            found = db.execute(
                "SELECT 1 FROM objects WHERE object_id=?",
                (object_id,),
            ).fetchone()
            if found is None:
                raise KeyError(object_id)
            db.execute(
                """INSERT INTO aliases(alias,object_id,updated_at) VALUES (?,?,?)
                   ON CONFLICT(alias) DO UPDATE SET
                   object_id=excluded.object_id, updated_at=excluded.updated_at""",
                (alias, object_id, now),
            )
            db.execute(
                """INSERT INTO alias_history(alias,object_id,updated_at)
                   VALUES (?,?,?)""",
                (alias, object_id, now),
            )

    def resolve(self, alias: str) -> StoredObject:
        with self._connect() as db:
            row = db.execute(
                "SELECT object_id FROM aliases WHERE alias=?",
                (alias,),
            ).fetchone()
        if row is None:
            raise KeyError(alias)
        return self.get(row["object_id"])

    def list_kind(self, kind: str) -> list[StoredObject]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT object_id FROM objects
                   WHERE kind=? ORDER BY created_at,object_id""",
                (kind,),
            ).fetchall()
        return [self.get(row["object_id"]) for row in rows]

    def provenance(self, object_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT source_type,source_ref,evidence_class,captured_at
                   FROM provenance WHERE object_id=? ORDER BY seq""",
                (object_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def counts(self) -> dict[str, int]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT kind,COUNT(*) AS n FROM objects GROUP BY kind"
            ).fetchall()
        return {row["kind"]: int(row["n"]) for row in rows}

    def ingest_many(
        self,
        kind: str,
        records: Iterable[Mapping[str, Any]],
        **provenance: Any,
    ) -> list[str]:
        return [
            self.put(kind, dict(record), **provenance)
            for record in records
        ]
