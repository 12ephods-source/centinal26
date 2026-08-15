from __future__ import annotations

import hashlib
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar


@dataclass(frozen=True)
class WatchDecision:
    """Result of one observation; ``notify`` means a delivery was durably enqueued."""

    target_key: str
    observed_state: str
    terminal: bool
    notify: bool
    first_terminal_state: str | None
    observation_count: int
    delivery_id: str | None = None
    delivery_state: str | None = None


@dataclass(frozen=True)
class DeliveryClaim:
    """A leased downstream notification delivery."""

    delivery_id: str
    target_key: str
    terminal_state: str
    attempt_count: int
    lease_owner: str
    lease_until: float


class ConditionWatchLedger:
    """Persistent terminal observation ledger with acknowledged delivery.

    Observation and delivery are distinct:

    ``terminal -> PENDING -> DELIVERING -> DELIVERED``

    A crash before acknowledgement leaves durable work that can be retried.
    """

    DELIVERY_STATES: ClassVar[set[str]] = {
        "PENDING",
        "DELIVERING",
        "DELIVERED",
        "FAILED_TERMINAL",
        "LEGACY_UNCERTAIN",
    }

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _clean(value: str, *, name: str) -> str:
        out = value.strip()
        if not out:
            raise ValueError(f"{name} must not be empty")
        return out

    @staticmethod
    def _delivery_id(target_key: str) -> str:
        digest = hashlib.sha256(f"condition-watch:{target_key}".encode()).hexdigest()
        return f"cwd-{digest[:32]}"

    @staticmethod
    def _ensure_column(
        db: sqlite3.Connection,
        *,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS condition_watches (
                    target_key TEXT PRIMARY KEY,
                    last_state TEXT NOT NULL,
                    first_terminal_state TEXT,
                    terminal_notified_at REAL,
                    observation_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS condition_watch_history (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_key TEXT NOT NULL,
                    observed_state TEXT NOT NULL,
                    terminal INTEGER NOT NULL,
                    notify INTEGER NOT NULL,
                    observed_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_condition_watch_history_target
                    ON condition_watch_history(target_key, seq);
                CREATE TABLE IF NOT EXISTS condition_watch_outbox (
                    delivery_id TEXT PRIMARY KEY,
                    target_key TEXT NOT NULL UNIQUE,
                    terminal_state TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    lease_owner TEXT,
                    lease_until REAL,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    delivered_at REAL,
                    FOREIGN KEY(target_key) REFERENCES condition_watches(target_key)
                );
                CREATE INDEX IF NOT EXISTS idx_condition_watch_outbox_ready
                    ON condition_watch_outbox(status, lease_until, created_at);
                """
            )
            self._ensure_column(
                db,
                table="condition_watches",
                column="terminal_enqueued_at",
                definition="REAL",
            )
            self._ensure_column(
                db,
                table="condition_watches",
                column="delivery_state",
                definition="TEXT",
            )
            self._ensure_column(
                db,
                table="condition_watch_history",
                column="delivery_id",
                definition="TEXT",
            )
            self._migrate_v1(db)

    def _migrate_v1(self, db: sqlite3.Connection) -> None:
        rows = db.execute(
            """
            SELECT target_key,first_terminal_state,terminal_notified_at
            FROM condition_watches
            WHERE terminal_notified_at IS NOT NULL AND terminal_enqueued_at IS NULL
            """
        ).fetchall()
        for row in rows:
            if row["first_terminal_state"] is None:
                continue
            key = row["target_key"]
            enqueued_at = float(row["terminal_notified_at"])
            delivery_id = self._delivery_id(key)
            db.execute(
                """
                INSERT OR IGNORE INTO condition_watch_outbox
                (delivery_id,target_key,terminal_state,status,attempt_count,
                 lease_owner,lease_until,last_error,created_at,updated_at,delivered_at)
                VALUES (?,?,?,'LEGACY_UNCERTAIN',0,NULL,NULL,NULL,?,?,NULL)
                """,
                (
                    delivery_id,
                    key,
                    row["first_terminal_state"],
                    enqueued_at,
                    enqueued_at,
                ),
            )
            db.execute(
                """
                UPDATE condition_watches
                SET terminal_enqueued_at=?,
                    terminal_notified_at=NULL,
                    delivery_state='LEGACY_UNCERTAIN'
                WHERE target_key=?
                """,
                (enqueued_at, key),
            )

    def observe(
        self,
        target_key: str,
        observed_state: str,
        *,
        terminal_states: Iterable[str],
        observed_at: float | None = None,
    ) -> WatchDecision:
        key = self._clean(target_key, name="target_key")
        state = self._clean(observed_state, name="observed_state")
        terminals = {self._clean(x, name="terminal_state") for x in terminal_states}
        if not terminals:
            raise ValueError("terminal_states must not be empty")
        now = time.time() if observed_at is None else float(observed_at)
        is_terminal = state in terminals
        notify = False
        delivery_id = None
        delivery_state = None

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM condition_watches WHERE target_key=?",
                (key,),
            ).fetchone()
            if row is None:
                first_terminal = state if is_terminal else None
                count = 1
                db.execute(
                    """
                    INSERT INTO condition_watches
                    (target_key,last_state,first_terminal_state,terminal_notified_at,
                     observation_count,created_at,updated_at,terminal_enqueued_at,delivery_state)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (key, state, first_terminal, None, count, now, now, None, None),
                )
            else:
                first_terminal = row["first_terminal_state"]
                count = int(row["observation_count"]) + 1
                db.execute(
                    """
                    UPDATE condition_watches
                    SET last_state=?,observation_count=?,updated_at=?
                    WHERE target_key=?
                    """,
                    (state, count, now, key),
                )

            if is_terminal:
                if first_terminal is None:
                    first_terminal = state
                    db.execute(
                        "UPDATE condition_watches SET first_terminal_state=? WHERE target_key=?",
                        (state, key),
                    )
                delivery_id = self._delivery_id(key)
                cur = db.execute(
                    """
                    INSERT OR IGNORE INTO condition_watch_outbox
                    (delivery_id,target_key,terminal_state,status,attempt_count,
                     lease_owner,lease_until,last_error,created_at,updated_at,delivered_at)
                    VALUES (?,?,?,'PENDING',0,NULL,NULL,NULL,?,?,NULL)
                    """,
                    (delivery_id, key, first_terminal, now, now),
                )
                notify = cur.rowcount == 1
                outbox = db.execute(
                    "SELECT status,created_at FROM condition_watch_outbox WHERE delivery_id=?",
                    (delivery_id,),
                ).fetchone()
                delivery_state = outbox["status"]
                db.execute(
                    """
                    UPDATE condition_watches
                    SET terminal_enqueued_at=COALESCE(terminal_enqueued_at,?),
                        delivery_state=?
                    WHERE target_key=?
                    """,
                    (float(outbox["created_at"]), delivery_state, key),
                )

            db.execute(
                """
                INSERT INTO condition_watch_history
                (target_key,observed_state,terminal,notify,observed_at,delivery_id)
                VALUES (?,?,?,?,?,?)
                """,
                (key, state, int(is_terminal), int(notify), now, delivery_id),
            )

        return WatchDecision(
            target_key=key,
            observed_state=state,
            terminal=is_terminal,
            notify=notify,
            first_terminal_state=first_terminal,
            observation_count=count,
            delivery_id=delivery_id,
            delivery_state=delivery_state,
        )

    def claim_delivery(
        self,
        worker_id: str,
        *,
        lease_seconds: float = 60.0,
        now: float | None = None,
        target_key: str | None = None,
    ) -> DeliveryClaim | None:
        worker = self._clean(worker_id, name="worker_id")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        current = time.time() if now is None else float(now)
        key = self._clean(target_key, name="target_key") if target_key is not None else None

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            predicate = """
                (status='PENDING'
                 OR (status='DELIVERING' AND lease_until IS NOT NULL AND lease_until<=?))
            """
            params: list[object] = [current]
            if key is not None:
                predicate += " AND target_key=?"
                params.append(key)
            row = db.execute(
                f"""
                SELECT * FROM condition_watch_outbox
                WHERE {predicate}
                ORDER BY created_at,delivery_id LIMIT 1
                """,
                tuple(params),
            ).fetchone()
            if row is None:
                return None
            lease_until = current + float(lease_seconds)
            attempt = int(row["attempt_count"]) + 1
            db.execute(
                """
                UPDATE condition_watch_outbox
                SET status='DELIVERING',attempt_count=?,lease_owner=?,lease_until=?,
                    updated_at=?,last_error=NULL
                WHERE delivery_id=?
                """,
                (attempt, worker, lease_until, current, row["delivery_id"]),
            )
            db.execute(
                """
                UPDATE condition_watches
                SET delivery_state='DELIVERING',updated_at=?
                WHERE target_key=?
                """,
                (current, row["target_key"]),
            )
            return DeliveryClaim(
                row["delivery_id"],
                row["target_key"],
                row["terminal_state"],
                attempt,
                worker,
                lease_until,
            )

    def acknowledge_delivery(
        self,
        delivery_id: str,
        worker_id: str,
        *,
        delivered_at: float | None = None,
    ) -> bool:
        did = self._clean(delivery_id, name="delivery_id")
        worker = self._clean(worker_id, name="worker_id")
        now = time.time() if delivered_at is None else float(delivered_at)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM condition_watch_outbox WHERE delivery_id=?",
                (did,),
            ).fetchone()
            if row is None:
                raise KeyError(did)
            if row["status"] == "DELIVERED":
                return False
            self._require_lease(row, worker)
            db.execute(
                """
                UPDATE condition_watch_outbox
                SET status='DELIVERED',lease_owner=NULL,lease_until=NULL,
                    delivered_at=?,updated_at=?,last_error=NULL
                WHERE delivery_id=?
                """,
                (now, now, did),
            )
            db.execute(
                """
                UPDATE condition_watches
                SET terminal_notified_at=?,delivery_state='DELIVERED',updated_at=?
                WHERE target_key=?
                """,
                (now, now, row["target_key"]),
            )
            return True

    def fail_delivery(
        self,
        delivery_id: str,
        worker_id: str,
        error: str,
        *,
        retryable: bool = True,
        failed_at: float | None = None,
    ) -> bool:
        did = self._clean(delivery_id, name="delivery_id")
        worker = self._clean(worker_id, name="worker_id")
        message = self._clean(error, name="error")
        now = time.time() if failed_at is None else float(failed_at)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM condition_watch_outbox WHERE delivery_id=?",
                (did,),
            ).fetchone()
            if row is None:
                raise KeyError(did)
            if row["status"] == "DELIVERED":
                return False
            self._require_lease(row, worker)
            status = "PENDING" if retryable else "FAILED_TERMINAL"
            db.execute(
                """
                UPDATE condition_watch_outbox
                SET status=?,lease_owner=NULL,lease_until=NULL,last_error=?,updated_at=?
                WHERE delivery_id=?
                """,
                (status, message[:4000], now, did),
            )
            db.execute(
                """
                UPDATE condition_watches SET delivery_state=?,updated_at=?
                WHERE target_key=?
                """,
                (status, now, row["target_key"]),
            )
            return True

    @staticmethod
    def _require_lease(row: sqlite3.Row, worker_id: str) -> None:
        if row["status"] != "DELIVERING":
            raise ValueError(f"delivery {row['delivery_id']} is not leased")
        if row["lease_owner"] != worker_id:
            raise PermissionError(
                f"delivery {row['delivery_id']} is leased by another worker"
            )

    def resolve_legacy(
        self,
        delivery_id: str,
        *,
        delivered: bool,
        resolved_at: float | None = None,
    ) -> None:
        did = self._clean(delivery_id, name="delivery_id")
        now = time.time() if resolved_at is None else float(resolved_at)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM condition_watch_outbox WHERE delivery_id=?",
                (did,),
            ).fetchone()
            if row is None:
                raise KeyError(did)
            if row["status"] != "LEGACY_UNCERTAIN":
                raise ValueError(f"delivery {did} is not legacy-uncertain")
            status = "DELIVERED" if delivered else "PENDING"
            delivered_at = now if delivered else None
            db.execute(
                """
                UPDATE condition_watch_outbox
                SET status=?,delivered_at=?,updated_at=?
                WHERE delivery_id=?
                """,
                (status, delivered_at, now, did),
            )
            db.execute(
                """
                UPDATE condition_watches
                SET terminal_notified_at=?,delivery_state=?,updated_at=?
                WHERE target_key=?
                """,
                (delivered_at, status, now, row["target_key"]),
            )

    def get(self, target_key: str) -> dict[str, object]:
        key = self._clean(target_key, name="target_key")
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM condition_watches WHERE target_key=?",
                (key,),
            ).fetchone()
        if row is None:
            raise KeyError(key)
        return dict(row)

    def delivery(self, delivery_id: str) -> dict[str, object]:
        did = self._clean(delivery_id, name="delivery_id")
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM condition_watch_outbox WHERE delivery_id=?",
                (did,),
            ).fetchone()
        if row is None:
            raise KeyError(did)
        return dict(row)

    def deliveries(self, *, status: str | None = None) -> tuple[dict[str, object], ...]:
        with self._connect() as db:
            if status is None:
                rows = db.execute(
                    "SELECT * FROM condition_watch_outbox ORDER BY created_at,delivery_id"
                ).fetchall()
            else:
                clean = self._clean(status, name="status")
                if clean not in self.DELIVERY_STATES:
                    raise ValueError(f"unsupported delivery status: {clean}")
                rows = db.execute(
                    """
                    SELECT * FROM condition_watch_outbox
                    WHERE status=? ORDER BY created_at,delivery_id
                    """,
                    (clean,),
                ).fetchall()
        return tuple(dict(row) for row in rows)

    def history(self, target_key: str) -> tuple[dict[str, object], ...]:
        key = self._clean(target_key, name="target_key")
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT seq,target_key,observed_state,terminal,notify,observed_at,delivery_id
                FROM condition_watch_history
                WHERE target_key=? ORDER BY seq
                """,
                (key,),
            ).fetchall()
        return tuple(dict(row) for row in rows)
