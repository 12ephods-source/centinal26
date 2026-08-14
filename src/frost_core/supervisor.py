from __future__ import annotations

import asyncio
import inspect
import json
import sqlite3
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TERMINAL_STATES = {"PASS", "REVIEW", "FAIL", "ERROR"}


@dataclass(frozen=True)
class SupervisorResult:
    state: str
    payload: Any

    def __post_init__(self) -> None:
        if self.state not in TERMINAL_STATES:
            raise ValueError(f"invalid supervisor result state: {self.state}")


Handler = Callable[
    [Mapping[str, Any]],
    SupervisorResult | Awaitable[SupervisorResult],
]


class LeaseQueue:
    """Durable idempotent SQLite queue with leases and bounded retry."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE,
                    priority INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    lease_owner TEXT,
                    lease_expires REAL,
                    result_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_ready
                    ON jobs(state, priority DESC, created_at);
                CREATE TABLE IF NOT EXISTS job_history (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    payload_json TEXT,
                    at REAL NOT NULL
                );
                """
            )

    def submit(
        self,
        operation: str,
        input_value: Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
        priority: int = 0,
        max_attempts: int = 3,
    ) -> str:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        now = time.time()
        payload = json.dumps(
            dict(input_value),
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._connect() as db:
            if idempotency_key:
                existing = db.execute(
                    "SELECT id FROM jobs WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    return str(existing["id"])
            job_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO jobs
                   (id,operation,input_json,idempotency_key,priority,state,
                    attempts,max_attempts,lease_owner,lease_expires,result_json,
                    created_at,updated_at)
                   VALUES (?,?,?,?,?,'QUEUED',0,?,NULL,NULL,NULL,?,?)""",
                (
                    job_id,
                    operation,
                    payload,
                    idempotency_key,
                    int(priority),
                    int(max_attempts),
                    now,
                    now,
                ),
            )
            db.execute(
                """INSERT INTO job_history(job_id,state,payload_json,at)
                   VALUES (?,?,?,?)""",
                (job_id, "QUEUED", payload, now),
            )
        return job_id

    def recover_expired(self, *, now: float | None = None) -> int:
        current = time.time() if now is None else float(now)
        recovered = 0
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                """SELECT id,attempts,max_attempts FROM jobs
                   WHERE state='RUNNING' AND lease_expires < ?""",
                (current,),
            ).fetchall()
            for row in rows:
                state = (
                    "QUEUED"
                    if row["attempts"] < row["max_attempts"]
                    else "ERROR"
                )
                result = json.dumps({"reason": "lease_expired"})
                db.execute(
                    """UPDATE jobs SET state=?,lease_owner=NULL,
                       lease_expires=NULL,result_json=?,updated_at=? WHERE id=?""",
                    (state, result, current, row["id"]),
                )
                db.execute(
                    """INSERT INTO job_history(job_id,state,payload_json,at)
                       VALUES (?,?,?,?)""",
                    (row["id"], state, result, current),
                )
                recovered += 1
        return recovered

    def claim(
        self,
        worker_id: str,
        *,
        lease_seconds: float = 60.0,
    ) -> dict[str, Any] | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT * FROM jobs WHERE state='QUEUED'
                   ORDER BY priority DESC,created_at,id LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            attempts = int(row["attempts"]) + 1
            db.execute(
                """UPDATE jobs SET state='RUNNING',attempts=?,lease_owner=?,
                   lease_expires=?,updated_at=?
                   WHERE id=? AND state='QUEUED'""",
                (
                    attempts,
                    worker_id,
                    now + lease_seconds,
                    now,
                    row["id"],
                ),
            )
            db.execute(
                """INSERT INTO job_history(job_id,state,payload_json,at)
                   VALUES (?,?,?,?)""",
                (
                    row["id"],
                    "RUNNING",
                    json.dumps({"worker_id": worker_id, "attempt": attempts}),
                    now,
                ),
            )
            result = dict(row)
            result["attempts"] = attempts
            result["input"] = json.loads(result.pop("input_json"))
            return result

    def heartbeat(
        self,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: float = 60.0,
    ) -> None:
        now = time.time()
        with self._connect() as db:
            cursor = db.execute(
                """UPDATE jobs SET lease_expires=?,updated_at=?
                   WHERE id=? AND state='RUNNING' AND lease_owner=?""",
                (now + lease_seconds, now, job_id, worker_id),
            )
            if cursor.rowcount != 1:
                raise PermissionError("job is not leased by this worker")

    def finish(
        self,
        job_id: str,
        worker_id: str,
        result: SupervisorResult,
    ) -> None:
        now = time.time()
        payload = json.dumps(
            result.payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT state,attempts,max_attempts,lease_owner
                   FROM jobs WHERE id=?""",
                (job_id,),
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["state"] != "RUNNING" or row["lease_owner"] != worker_id:
                raise PermissionError("job is not leased by this worker")
            state = result.state
            if state == "ERROR" and row["attempts"] < row["max_attempts"]:
                state = "QUEUED"
            db.execute(
                """UPDATE jobs SET state=?,result_json=?,lease_owner=NULL,
                   lease_expires=NULL,updated_at=? WHERE id=?""",
                (state, payload, now, job_id),
            )
            db.execute(
                """INSERT INTO job_history(job_id,state,payload_json,at)
                   VALUES (?,?,?,?)""",
                (job_id, state, payload, now),
            )

    def get(self, job_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        result = dict(row)
        result["input"] = json.loads(result.pop("input_json"))
        raw_result = result.pop("result_json")
        result["result"] = (
            None if raw_result is None else json.loads(raw_result)
        )
        return result


class AsyncSupervisor:
    """Bounded async dispatcher; evaluated FAIL is never retried."""

    def __init__(
        self,
        queue: LeaseQueue,
        handlers: Mapping[str, Handler],
        *,
        worker_id: str = "local-supervisor",
        max_concurrency: int = 4,
        lease_seconds: float = 60.0,
    ):
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self.queue = queue
        self.handlers = dict(handlers)
        self.worker_id = worker_id
        self.max_concurrency = max_concurrency
        self.lease_seconds = lease_seconds

    async def _run_claimed(self, job: Mapping[str, Any]) -> str:
        job_id = str(job["id"])
        operation = str(job["operation"])
        handler = self.handlers.get(operation)
        if handler is None:
            self.queue.finish(
                job_id,
                self.worker_id,
                SupervisorResult(
                    "FAIL",
                    {
                        "error": "unregistered_operation",
                        "operation": operation,
                    },
                ),
            )
            return job_id
        try:
            value = handler(job["input"])
            result = await value if inspect.isawaitable(value) else value
            if not isinstance(result, SupervisorResult):
                raise TypeError("handler must return SupervisorResult")
        except Exception as exc:  # noqa: BLE001 - execution boundary
            result = SupervisorResult(
                "ERROR",
                {"error": type(exc).__name__, "message": str(exc)},
            )
        self.queue.finish(job_id, self.worker_id, result)
        return job_id

    async def run_batch(self) -> list[str]:
        self.queue.recover_expired()
        claimed: list[dict[str, Any]] = []
        for _ in range(self.max_concurrency):
            job = self.queue.claim(
                self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if job is None:
                break
            claimed.append(job)
        if not claimed:
            return []
        return list(
            await asyncio.gather(
                *(self._run_claimed(job) for job in claimed)
            )
        )

    async def run_until_idle(self, *, max_batches: int = 1000) -> int:
        processed = 0
        for _ in range(max_batches):
            batch = await self.run_batch()
            if not batch:
                break
            processed += len(batch)
        return processed
