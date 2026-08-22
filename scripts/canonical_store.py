"""Append-only SQLite store for Dedupe/Organizer canonical objects.

The store is intentionally narrow: it persists invariant-valid canonical bundles,
rejects identity/content mutation, and exposes only rebuildable projections.
It performs no deletion/remediation and makes no semantic truth promotions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Self

from validate_canonical_kernel import validate_bundle

SCHEMA_VERSION = 1

DDL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS canonical_objects (
    object_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    object_type TEXT NOT NULL,
    status TEXT NOT NULL,
    epistemic_status TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    authority_class TEXT NOT NULL,
    authoritative INTEGER NOT NULL CHECK (authoritative IN (0, 1)),
    confidence REAL NOT NULL,
    ingested_at TEXT NOT NULL,
    envelope_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provenance_events (
    provenance_event_id TEXT PRIMARY KEY,
    event_hash TEXT NOT NULL,
    event_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS object_provenance (
    object_id TEXT NOT NULL REFERENCES canonical_objects(object_id),
    provenance_event_id TEXT NOT NULL REFERENCES provenance_events(provenance_event_id),
    PRIMARY KEY (object_id, provenance_event_id)
);
CREATE TABLE IF NOT EXISTS filter_decisions (
    filter_decision_id TEXT PRIMARY KEY,
    input_object_id TEXT NOT NULL REFERENCES canonical_objects(object_id),
    decision TEXT NOT NULL,
    canonical_target_id TEXT,
    decision_hash TEXT NOT NULL,
    decision_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS object_projection (
    object_id TEXT PRIMARY KEY,
    object_type TEXT NOT NULL,
    status TEXT NOT NULL,
    epistemic_status TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    search_text TEXT NOT NULL,
    authoritative INTEGER NOT NULL DEFAULT 0 CHECK (authoritative = 0)
);
"""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _payload_search_text(obj: dict[str, Any]) -> str:
    payload = obj.get("payload", {})
    return _canonical_json(payload)


class CanonicalStoreError(RuntimeError):
    """Raised when canonical-store invariants would be violated."""


class CanonicalStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(DDL)
            row = self.conn.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                self.conn.execute(
                    "INSERT INTO metadata(key, value) VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            elif int(row["value"]) != SCHEMA_VERSION:
                raise CanonicalStoreError(
                    f"unsupported store schema {row['value']}; expected {SCHEMA_VERSION}"
                )

    def ingest_bundle(self, bundle: dict[str, Any]) -> dict[str, int]:
        errors = validate_bundle(bundle)
        if errors:
            raise CanonicalStoreError("bundle invariant failure: " + "; ".join(errors))

        counts = {"objects": 0, "provenance_events": 0, "filter_decisions": 0}
        try:
            with self.conn:
                for obj in bundle.get("objects", []):
                    counts["objects"] += self._insert_object(obj)
                for event in bundle.get("provenance_events", []):
                    counts["provenance_events"] += self._insert_provenance(event)
                for obj in bundle.get("objects", []):
                    for pid in obj.get("provenance_ids", []):
                        self.conn.execute(
                            "INSERT OR IGNORE INTO object_provenance"
                            "(object_id, provenance_event_id) VALUES(?, ?)",
                            (obj["object_id"], pid),
                        )
                for decision in bundle.get("filter_decisions", []):
                    counts["filter_decisions"] += self._insert_filter_decision(decision)
        except sqlite3.IntegrityError as exc:
            raise CanonicalStoreError(f"transaction rejected: {exc}") from exc
        return counts

    def _insert_object(self, obj: dict[str, Any]) -> int:
        oid = obj["object_id"]
        envelope_json = _canonical_json(obj)
        existing = self.conn.execute(
            "SELECT content_hash, envelope_json FROM canonical_objects WHERE object_id=?",
            (oid,),
        ).fetchone()
        if existing is not None:
            if existing["content_hash"] != obj["content_hash"]:
                raise CanonicalStoreError(
                    f"immutable object_id {oid} already exists with different content_hash"
                )
            if existing["envelope_json"] != envelope_json:
                raise CanonicalStoreError(
                    f"immutable object_id {oid} already exists with different envelope"
                )
            return 0
        self.conn.execute(
            "INSERT INTO canonical_objects("
            "object_id, content_hash, object_type, status, epistemic_status, "
            "verification_status, authority_class, authoritative, confidence, "
            "ingested_at, envelope_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                oid,
                obj["content_hash"],
                obj["type"],
                obj["status"],
                obj["epistemic_status"],
                obj["verification_status"],
                obj["authority_class"],
                int(bool(obj["authoritative"])),
                float(obj["confidence"]),
                obj["ingested_at"],
                envelope_json,
            ),
        )
        return 1

    def _insert_provenance(self, event: dict[str, Any]) -> int:
        pid = event["provenance_event_id"]
        event_json = _canonical_json(event)
        event_hash = _sha256_json(event)
        existing = self.conn.execute(
            "SELECT event_hash, event_json FROM provenance_events WHERE provenance_event_id=?",
            (pid,),
        ).fetchone()
        if existing is not None:
            if existing["event_hash"] != event_hash or existing["event_json"] != event_json:
                raise CanonicalStoreError(
                    f"immutable provenance_event_id {pid} already exists with different content"
                )
            return 0
        self.conn.execute(
            "INSERT INTO provenance_events(provenance_event_id, event_hash, event_json) "
            "VALUES(?, ?, ?)",
            (pid, event_hash, event_json),
        )
        return 1

    def _insert_filter_decision(self, decision: dict[str, Any]) -> int:
        did = decision["filter_decision_id"]
        decision_json = _canonical_json(decision)
        decision_hash = _sha256_json(decision)
        existing = self.conn.execute(
            "SELECT decision_hash, decision_json FROM filter_decisions WHERE filter_decision_id=?",
            (did,),
        ).fetchone()
        if existing is not None:
            if (
                existing["decision_hash"] != decision_hash
                or existing["decision_json"] != decision_json
            ):
                raise CanonicalStoreError(
                    f"immutable filter_decision_id {did} already exists with different content"
                )
            return 0
        self.conn.execute(
            "INSERT INTO filter_decisions("
            "filter_decision_id, input_object_id, decision, canonical_target_id, "
            "decision_hash, decision_json) VALUES(?, ?, ?, ?, ?, ?)",
            (
                did,
                decision["input_object_id"],
                decision["decision"],
                decision.get("canonical_target_id"),
                decision_hash,
                decision_json,
            ),
        )
        return 1

    def rebuild_projection(self) -> int:
        rows = self.conn.execute("SELECT envelope_json FROM canonical_objects").fetchall()
        with self.conn:
            self.conn.execute("DELETE FROM object_projection")
            for row in rows:
                obj = json.loads(row["envelope_json"])
                self.conn.execute(
                    "INSERT INTO object_projection("
                    "object_id, object_type, status, epistemic_status, verification_status, "
                    "search_text, authoritative) VALUES(?, ?, ?, ?, ?, ?, 0)",
                    (
                        obj["object_id"],
                        obj["type"],
                        obj["status"],
                        obj["epistemic_status"],
                        obj["verification_status"],
                        _payload_search_text(obj),
                    ),
                )
        return len(rows)

    def get_object(self, object_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT envelope_json FROM canonical_objects WHERE object_id=?", (object_id,)
        ).fetchone()
        return None if row is None else json.loads(row["envelope_json"])

    def search_projection(self, text: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT object_id, object_type, status, epistemic_status, verification_status "
            "FROM object_projection WHERE search_text LIKE ? ORDER BY object_id",
            (f"%{text}%",),
        ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, int]:
        tables = [
            "canonical_objects",
            "provenance_events",
            "object_provenance",
            "filter_decisions",
            "object_projection",
        ]
        return {
            table: int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalStoreError(f"cannot read bundle: {exc}") from exc
    if not isinstance(value, dict):
        raise CanonicalStoreError("bundle root must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("bundle", type=Path)
    sub.add_parser("stats")
    sub.add_parser("rebuild-projection")
    get_cmd = sub.add_parser("get")
    get_cmd.add_argument("object_id")
    search = sub.add_parser("search")
    search.add_argument("text")
    args = parser.parse_args()

    try:
        with CanonicalStore(args.db) as store:
            if args.command == "ingest":
                print(json.dumps(store.ingest_bundle(_load_json(args.bundle)), sort_keys=True))
            elif args.command == "stats":
                print(json.dumps(store.stats(), sort_keys=True))
            elif args.command == "rebuild-projection":
                print(json.dumps({"projection_rows": store.rebuild_projection()}))
            elif args.command == "get":
                obj = store.get_object(args.object_id)
                if obj is None:
                    return 1
                print(json.dumps(obj, indent=2, sort_keys=True))
            elif args.command == "search":
                print(json.dumps(store.search_projection(args.text), indent=2, sort_keys=True))
    except CanonicalStoreError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
