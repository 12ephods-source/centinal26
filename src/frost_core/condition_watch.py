from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class WatchDecision:
    """Result of one condition observation.

    ``notify`` is true exactly once for a given immutable target key: the first
    observation whose state is terminal. Repeated polling, retries, or later
    contradictory observations never produce a second terminal notification.
    A changed external target (for example a new commit SHA) must use a new key.
    """

    target_key: str
    observed_state: str
    terminal: bool
    notify: bool
    first_terminal_state: str | None
    observation_count: int


class ConditionWatchLedger:
    """Persistent exactly-once terminal-condition ledger.

    The ledger deliberately separates polling cadence from notification
    semantics. Providers may poll at any cadence, but a terminal event is
    emitted at most once per immutable ``target_key``.

    SQLite ``BEGIN IMMEDIATE`` serialization makes the first-terminal decision
    atomic across concurrent workers sharing the database.
    """

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
                """
            )

    @staticmethod
    def _clean(value: str, *, name: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{name} must not be empty")
        return cleaned

    def observe(
        self,
        target_key: str,
        observed_state: str,
        *,
        terminal_states: Iterable[str],
        observed_at: float | None = None,
    ) -> WatchDecision:
        """Record one observation and atomically decide whether to notify.

        ``terminal_states`` is supplied by the caller so the shared ledger does
        not encode provider-specific status vocabularies.
        """

        key = self._clean(target_key, name="target_key")
        state = self._clean(observed_state, name="observed_state")
        terminals = {self._clean(item, name="terminal_state") for item in terminal_states}
        if not terminals:
            raise ValueError("terminal_states must not be empty")

        now = time.time() if observed_at is None else float(observed_at)
        is_terminal = state in terminals

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM condition_watches WHERE target_key=?",
                (key,),
            ).fetchone()

            if row is None:
                first_terminal_state = state if is_terminal else None
                notified_at = now if is_terminal else None
                count = 1
                notify = is_terminal
                db.execute(
                    """INSERT INTO condition_watches
                       (target_key,last_state,first_terminal_state,
                        terminal_notified_at,observation_count,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        key,
                        state,
                        first_terminal_state,
                        notified_at,
                        count,
                        now,
                        now,
                    ),
                )
            else:
                already_notified = row["terminal_notified_at"] is not None
                notify = bool(is_terminal and not already_notified)
                first_terminal_state = row["first_terminal_state"]
                if notify:
                    first_terminal_state = state
                count = int(row["observation_count"]) + 1
                db.execute(
                    """UPDATE condition_watches
                       SET last_state=?,
                           first_terminal_state=?,
                           terminal_notified_at=CASE
                               WHEN terminal_notified_at IS NULL AND ?=1 THEN ?
                               ELSE terminal_notified_at
                           END,
                           observation_count=?,
                           updated_at=?
                       WHERE target_key=?""",
                    (
                        state,
                        first_terminal_state,
                        int(is_terminal),
                        now,
                        count,
                        now,
                        key,
                    ),
                )

            db.execute(
                """INSERT INTO condition_watch_history
                   (target_key,observed_state,terminal,notify,observed_at)
                   VALUES (?,?,?,?,?)""",
                (key, state, int(is_terminal), int(notify), now),
            )

        return WatchDecision(
            target_key=key,
            observed_state=state,
            terminal=is_terminal,
            notify=notify,
            first_terminal_state=first_terminal_state,
            observation_count=count,
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

    def history(self, target_key: str) -> tuple[dict[str, object], ...]:
        key = self._clean(target_key, name="target_key")
        with self._connect() as db:
            rows = db.execute(
                """SELECT seq,target_key,observed_state,terminal,notify,observed_at
                   FROM condition_watch_history
                   WHERE target_key=? ORDER BY seq""",
                (key,),
            ).fetchall()
        return tuple(dict(row) for row in rows)
