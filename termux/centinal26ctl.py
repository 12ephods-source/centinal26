from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

ROOT = Path(os.environ.get("CENTINAL26_HOME", str(Path.home() / ".centinal26")))
DB = ROOT / "state" / "daemon.sqlite3"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS task (
 id TEXT PRIMARY KEY,intent TEXT NOT NULL,capability TEXT NOT NULL,payload_json TEXT NOT NULL,
 idempotency_key TEXT NOT NULL UNIQUE,state TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,
 lease_owner TEXT,lease_until INTEGER,attempt_count INTEGER NOT NULL DEFAULT 0,next_attempt_at INTEGER NOT NULL DEFAULT 0,
 source_revision TEXT,last_error TEXT);
CREATE TABLE IF NOT EXISTS evidence (
 id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL,ts INTEGER NOT NULL,kind TEXT NOT NULL,payload_json TEXT NOT NULL,sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS daemon_state (key TEXT PRIMARY KEY,value TEXT NOT NULL);
"""


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def enqueue(args: argparse.Namespace) -> None:
    payload = json.loads(args.payload)
    now = int(time.time())
    canonical = json.dumps(
        {"intent": args.intent, "capability": args.capability, "payload": payload},
        sort_keys=True,
    ).encode()
    idem = args.idempotency_key or hashlib.sha256(canonical).hexdigest()
    task_id = args.task_id or str(uuid.uuid4())
    con = connect()
    try:
        con.execute(
            "INSERT INTO task(id,intent,capability,payload_json,idempotency_key,state,created_at,updated_at,next_attempt_at,source_revision) "
            "VALUES(?,?,?,?,?,'QUEUED',?,?,?,?,?)",
            (
                task_id,
                args.intent,
                args.capability,
                json.dumps(payload, sort_keys=True),
                idem,
                now,
                now,
                0,
                args.source_revision,
            ),
        )
        con.commit()
        print(json.dumps({"status": "QUEUED", "task_id": task_id, "idempotency_key": idem}, sort_keys=True))
    except sqlite3.IntegrityError:
        row = con.execute("SELECT id,state FROM task WHERE idempotency_key=?", (idem,)).fetchone()
        print(
            json.dumps(
                {
                    "status": "ALREADY_EXISTS",
                    "task_id": row["id"],
                    "state": row["state"],
                    "idempotency_key": idem,
                },
                sort_keys=True,
            )
        )


def status(args: argparse.Namespace) -> None:
    con = connect()
    if args.task_id:
        row = con.execute("SELECT * FROM task WHERE id=?", (args.task_id,)).fetchone()
        print(json.dumps(dict(row) if row else {"status": "NOT_FOUND"}, sort_keys=True))
        return
    rows = [
        dict(row)
        for row in con.execute(
            "SELECT id,intent,capability,state,attempt_count,updated_at,last_error "
            "FROM task ORDER BY created_at DESC LIMIT ?",
            (args.limit,),
        )
    ]
    health = con.execute("SELECT value FROM daemon_state WHERE key='health'").fetchone()
    print(
        json.dumps(
            {"health": json.loads(health[0]) if health else None, "tasks": rows},
            sort_keys=True,
        )
    )


def show_evidence(args: argparse.Namespace) -> None:
    con = connect()
    rows = [
        dict(row)
        for row in con.execute(
            "SELECT ts,kind,payload_json,sha256 FROM evidence WHERE task_id=? ORDER BY id",
            (args.task_id,),
        )
    ]
    for row in rows:
        row["payload"] = json.loads(row.pop("payload_json"))
    print(json.dumps({"task_id": args.task_id, "evidence": rows}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    queue = sub.add_parser("enqueue")
    queue.add_argument("--intent", required=True)
    queue.add_argument("--capability", required=True)
    queue.add_argument("--payload", required=True)
    queue.add_argument("--idempotency-key")
    queue.add_argument("--task-id")
    queue.add_argument("--source-revision")
    queue.set_defaults(fn=enqueue)

    stat = sub.add_parser("status")
    stat.add_argument("--task-id")
    stat.add_argument("--limit", type=int, default=20)
    stat.set_defaults(fn=status)

    ev = sub.add_parser("evidence")
    ev.add_argument("task_id")
    ev.set_defaults(fn=show_evidence)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
