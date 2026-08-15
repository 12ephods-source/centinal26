from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

GENESIS_HASH = "0" * 64
REVIEW_CLASSES = ("P0", "P1", "P2", "P3")
SEVERITY_ORDER = {"INFO": 10, "LOW": 20, "MEDIUM": 30, "HIGH": 40, "CRITICAL": 50}


@dataclass(frozen=True)
class CadencePolicy:
    policy_key: str
    event_class: str
    dispatch_class: str
    max_delay_seconds: int
    priority: int
    requires_ai: bool = True
    requires_material_change: bool = False


DEFAULT_POLICIES = (
    CadencePolicy(
        "critical-contradiction-immediate",
        "CRITICAL_CONTRADICTION",
        "IMMEDIATE",
        0,
        110,
        requires_material_change=True,
    ),
    CadencePolicy(
        "new-evidence-immediate",
        "NEW_EVIDENCE",
        "IMMEDIATE",
        0,
        105,
        requires_material_change=True,
    ),
    CadencePolicy(
        "state-change-immediate",
        "STATE_CHANGE",
        "IMMEDIATE",
        0,
        100,
        requires_material_change=True,
    ),
    CadencePolicy("ordinary-review-batch", "ORDINARY_REVIEW", "BATCH_10M", 600, 50),
    CadencePolicy("deep-synthesis-hourly", "DEEP_SYNTHESIS", "HOURLY", 3600, 40),
    CadencePolicy("portfolio-review-daily", "PORTFOLIO_REVIEW", "DAILY", 86400, 30),
    CadencePolicy("full-corpus-audit-weekly", "FULL_CORPUS_AUDIT", "WEEKLY", 604800, 20),
    CadencePolicy(
        "architecture-review-monthly",
        "ARCHITECTURE_REVIEW",
        "MONTHLY",
        31 * 86400,
        10,
    ),
    CadencePolicy(
        "scientific-compatibility-daily",
        "SCIENTIFIC_COMPATIBILITY",
        "DAILY",
        86400,
        25,
    ),
)


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS cadence_policy (
    policy_key TEXT PRIMARY KEY,
    event_class TEXT NOT NULL UNIQUE,
    dispatch_class TEXT NOT NULL,
    max_delay_seconds INTEGER NOT NULL,
    priority INTEGER NOT NULL,
    requires_ai INTEGER NOT NULL,
    requires_material_change INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS source_snapshots (
    source_kind TEXT NOT NULL,
    source_key TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY(source_kind, source_key)
);
CREATE TABLE IF NOT EXISTS change_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    detected_at TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_key TEXT NOT NULL,
    change_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    dispatch_class TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    previous_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    contradiction_json TEXT NOT NULL,
    prev_event_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS change_events_no_update
BEFORE UPDATE ON change_events BEGIN
    SELECT RAISE(ABORT, 'change events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS change_events_no_delete
BEFORE DELETE ON change_events BEGIN
    SELECT RAISE(ABORT, 'change events are append-only');
END;
CREATE TABLE IF NOT EXISTS event_processing (
    event_key TEXT PRIMARY KEY REFERENCES change_events(event_key),
    status TEXT NOT NULL,
    processed_at TEXT,
    result_json TEXT
);
CREATE TABLE IF NOT EXISTS conversations (
    conversation_key TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    project TEXT NOT NULL,
    review_class TEXT NOT NULL,
    strategic_value REAL NOT NULL,
    status TEXT NOT NULL,
    last_reviewed_week TEXT,
    last_reviewed_at TEXT,
    review_count INTEGER NOT NULL DEFAULT 0,
    unresolved_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS conversation_reviews (
    conversation_key TEXT NOT NULL REFERENCES conversations(conversation_key),
    week_id TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    unique_signal TEXT NOT NULL,
    contradiction TEXT NOT NULL,
    open_loop TEXT NOT NULL,
    decision TEXT NOT NULL,
    implementation_state TEXT NOT NULL,
    architectural_implication TEXT NOT NULL,
    confidence REAL NOT NULL,
    source_basis TEXT NOT NULL,
    review_hash TEXT NOT NULL,
    PRIMARY KEY(conversation_key, week_id)
);
CREATE TABLE IF NOT EXISTS work_items (
    work_key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    dispatch_class TEXT NOT NULL,
    priority INTEGER NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    source_event_key TEXT REFERENCES change_events(event_key),
    claimed_by TEXT,
    lease_until TEXT,
    completed_at TEXT,
    result_json TEXT
);
CREATE TABLE IF NOT EXISTS controller_cycles (
    cycle_key TEXT PRIMARY KEY,
    run_at TEXT NOT NULL,
    local_window TEXT NOT NULL,
    coverage_json TEXT NOT NULL,
    due_work_json TEXT NOT NULL,
    event_chain_valid INTEGER NOT NULL,
    cycle_hash TEXT NOT NULL
);
"""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _event_hash(body: dict[str, Any]) -> str:
    return sha256_json(body)


class IntelligenceController:
    """Persistent, provider-neutral event-latency controller.

    It schedules work but deliberately does not grant execution authority. Providers such as
    ChatGPT, Base44, Termux workers, or future model gateways may claim bounded work items and
    return results through the ledger.
    """

    def __init__(
        self,
        path: Path,
        *,
        timezone_name: str = "America/Mexico_City",
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.timezone_name = timezone_name
        self.timezone = ZoneInfo(timezone_name)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._seed_policies()

    def close(self) -> None:
        self.db.close()

    def _seed_policies(self) -> None:
        self.db.executemany(
            """INSERT OR IGNORE INTO cadence_policy (
                policy_key,event_class,dispatch_class,max_delay_seconds,priority,
                requires_ai,requires_material_change,enabled
            ) VALUES (?,?,?,?,?,?,?,1)""",
            [
                (
                    p.policy_key,
                    p.event_class,
                    p.dispatch_class,
                    p.max_delay_seconds,
                    p.priority,
                    int(p.requires_ai),
                    int(p.requires_material_change),
                )
                for p in DEFAULT_POLICIES
            ],
        )
        self.db.commit()

    def _policy(self, event_class: str) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM cadence_policy WHERE event_class=? AND enabled=1",
            (event_class,),
        ).fetchone()
        if row is None:
            raise KeyError(f"no enabled cadence policy for {event_class}")
        return row

    def _local(self, now: datetime) -> datetime:
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        return now.astimezone(self.timezone)

    def week_id(self, now: datetime | None = None) -> str:
        local = self._local(now or _utc_now())
        year, week, _ = local.isocalendar()
        return f"{year}-W{week:02d}"

    def register_conversation(
        self,
        conversation_key: str,
        title: str,
        *,
        project: str = "Automation",
        review_class: str = "P2",
        strategic_value: float = 0.5,
        status: str = "ACTIVE",
        unresolved_count: int = 0,
        notes: str = "",
    ) -> None:
        if review_class not in REVIEW_CLASSES:
            raise ValueError(f"invalid review class: {review_class}")
        if not 0.0 <= strategic_value <= 1.0:
            raise ValueError("strategic_value must be in [0, 1]")
        if unresolved_count < 0:
            raise ValueError("unresolved_count must be non-negative")
        self.db.execute(
            """INSERT INTO conversations (
                conversation_key,title,project,review_class,strategic_value,status,
                unresolved_count,notes
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(conversation_key) DO UPDATE SET
                title=excluded.title,
                project=excluded.project,
                review_class=excluded.review_class,
                strategic_value=excluded.strategic_value,
                status=excluded.status,
                unresolved_count=excluded.unresolved_count,
                notes=excluded.notes""",
            (
                conversation_key,
                title,
                project,
                review_class,
                strategic_value,
                status,
                unresolved_count,
                notes,
            ),
        )
        self.db.commit()

    def import_registry(self, records: list[dict[str, Any]]) -> int:
        for record in records:
            self.register_conversation(
                str(record["conversation_key"]),
                str(record["title"]),
                project=str(record.get("project", "Automation")),
                review_class=str(record.get("review_class", "P2")),
                strategic_value=float(record.get("strategic_value", 0.5)),
                status=str(record.get("status", "ACTIVE")),
                unresolved_count=int(record.get("unresolved_count", 0)),
                notes=str(record.get("notes", "")),
            )
            if record.get("last_reviewed_week"):
                self.db.execute(
                    """UPDATE conversations SET last_reviewed_week=?, last_reviewed_at=?,
                    review_count=? WHERE conversation_key=?""",
                    (
                        record.get("last_reviewed_week"),
                        record.get("last_reviewed_at"),
                        int(record.get("review_count", 0)),
                        record["conversation_key"],
                    ),
                )
        self.db.commit()
        return len(records)

    def next_conversation(self, now: datetime | None = None) -> dict[str, Any] | None:
        week = self.week_id(now)
        row = self.db.execute(
            """SELECT * FROM conversations
            WHERE project='Automation' AND COALESCE(last_reviewed_week,'') != ?
            ORDER BY CASE review_class
                WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END,
                strategic_value DESC, conversation_key ASC
            LIMIT 1""",
            (week,),
        ).fetchone()
        return dict(row) if row else None

    def record_review(
        self,
        conversation_key: str,
        *,
        unique_signal: str,
        contradiction: str,
        open_loop: str,
        decision: str,
        implementation_state: str,
        architectural_implication: str,
        confidence: float,
        source_basis: str,
        now: datetime | None = None,
    ) -> str:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        now = now or _utc_now()
        reviewed_at = _iso(now)
        week = self.week_id(now)
        body = {
            "conversation_key": conversation_key,
            "week_id": week,
            "reviewed_at": reviewed_at,
            "unique_signal": unique_signal,
            "contradiction": contradiction,
            "open_loop": open_loop,
            "decision": decision,
            "implementation_state": implementation_state,
            "architectural_implication": architectural_implication,
            "confidence": confidence,
            "source_basis": source_basis,
        }
        digest = sha256_json(body)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            exists = self.db.execute(
                "SELECT 1 FROM conversations WHERE conversation_key=?", (conversation_key,)
            ).fetchone()
            if exists is None:
                raise KeyError(f"unknown conversation: {conversation_key}")
            self.db.execute(
                """INSERT OR REPLACE INTO conversation_reviews (
                    conversation_key,week_id,reviewed_at,unique_signal,contradiction,open_loop,
                    decision,implementation_state,architectural_implication,confidence,source_basis,
                    review_hash
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    conversation_key,
                    week,
                    reviewed_at,
                    unique_signal,
                    contradiction,
                    open_loop,
                    decision,
                    implementation_state,
                    architectural_implication,
                    confidence,
                    source_basis,
                    digest,
                ),
            )
            self.db.execute(
                """UPDATE conversations SET last_reviewed_week=?, last_reviewed_at=?,
                review_count=review_count+1 WHERE conversation_key=?""",
                (week, reviewed_at, conversation_key),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return digest

    def coverage(self, now: datetime | None = None) -> dict[str, Any]:
        week = self.week_id(now)
        rows = self.db.execute(
            "SELECT review_class,last_reviewed_week FROM conversations WHERE project='Automation'"
        ).fetchall()
        total = len(rows)
        reviewed = sum(row["last_reviewed_week"] == week for row in rows)
        remaining = total - reviewed
        class_remaining = {
            cls: sum(
                row["review_class"] == cls and row["last_reviewed_week"] != week for row in rows
            )
            for cls in REVIEW_CLASSES
        }
        return {
            "week_id": week,
            "total_registered": total,
            "reviewed_count": reviewed,
            "remaining_count": remaining,
            "coverage_fraction": reviewed / total if total else 1.0,
            "remaining_by_class": class_remaining,
            "next_conversation": (self.next_conversation(now) or {}).get("conversation_key"),
        }

    def observe(
        self,
        *,
        source_kind: str,
        source_key: str,
        change_type: str,
        severity: str,
        evidence: dict[str, Any],
        contradiction: dict[str, Any] | None = None,
        material_change: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        if severity not in SEVERITY_ORDER:
            raise ValueError(f"invalid severity: {severity}")
        now = now or _utc_now()
        detected_at = _iso(now)
        current_hash = sha256_json(evidence)
        previous = self.db.execute(
            "SELECT content_hash FROM source_snapshots WHERE source_kind=? AND source_key=?",
            (source_kind, source_key),
        ).fetchone()
        previous_hash = previous["content_hash"] if previous else GENESIS_HASH
        if current_hash == previous_hash:
            return None

        event_class = change_type
        if change_type in {"STATE_CHANGE", "CRITICAL_CONTRADICTION", "NEW_EVIDENCE"}:
            policy = self._policy(change_type)
        else:
            policy = self._policy("ORDINARY_REVIEW")
        if bool(policy["requires_material_change"]) and not material_change:
            policy = self._policy("ORDINARY_REVIEW")

        dedupe_key = f"{source_kind}:{source_key}:{change_type}:{current_hash}"
        event_key = f"change:{hashlib.sha256(dedupe_key.encode()).hexdigest()[:32]}"
        contradiction = contradiction or {}
        latest = self.db.execute(
            "SELECT event_hash FROM change_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_event_hash = latest["event_hash"] if latest else GENESIS_HASH
        body = {
            "event_key": event_key,
            "detected_at": detected_at,
            "source_kind": source_kind,
            "source_key": source_key,
            "change_type": event_class,
            "severity": severity,
            "dispatch_class": policy["dispatch_class"],
            "dedupe_key": dedupe_key,
            "previous_hash": previous_hash,
            "current_hash": current_hash,
            "evidence": evidence,
            "contradiction": contradiction,
            "prev_event_hash": prev_event_hash,
        }
        digest = _event_hash(body)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                """INSERT OR IGNORE INTO change_events (
                    event_key,detected_at,source_kind,source_key,change_type,severity,
                    dispatch_class,dedupe_key,previous_hash,current_hash,evidence_json,
                    contradiction_json,prev_event_hash,event_hash
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event_key,
                    detected_at,
                    source_kind,
                    source_key,
                    event_class,
                    severity,
                    policy["dispatch_class"],
                    dedupe_key,
                    previous_hash,
                    current_hash,
                    canonical_json(evidence),
                    canonical_json(contradiction),
                    prev_event_hash,
                    digest,
                ),
            )
            self.db.execute(
                """INSERT INTO source_snapshots (
                    source_kind,source_key,content_hash,payload_json,observed_at
                ) VALUES (?,?,?,?,?)
                ON CONFLICT(source_kind,source_key) DO UPDATE SET
                    content_hash=excluded.content_hash,
                    payload_json=excluded.payload_json,
                    observed_at=excluded.observed_at""",
                (source_kind, source_key, current_hash, canonical_json(evidence), detected_at),
            )
            self._enqueue_work(
                work_key=f"event:{event_key}",
                created_at=detected_at,
                due_at=detected_at,
                kind="CHANGE_EVENT",
                dispatch_class=str(policy["dispatch_class"]),
                priority=int(policy["priority"]) + SEVERITY_ORDER[severity],
                payload={"event_key": event_key, "change_type": change_type},
                source_event_key=event_key,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {**body, "event_hash": digest}

    def verify_event_chain(self) -> bool:
        previous = GENESIS_HASH
        for row in self.db.execute("SELECT * FROM change_events ORDER BY seq"):
            if row["prev_event_hash"] != previous:
                return False
            body = {
                "event_key": row["event_key"],
                "detected_at": row["detected_at"],
                "source_kind": row["source_kind"],
                "source_key": row["source_key"],
                "change_type": row["change_type"],
                "severity": row["severity"],
                "dispatch_class": row["dispatch_class"],
                "dedupe_key": row["dedupe_key"],
                "previous_hash": row["previous_hash"],
                "current_hash": row["current_hash"],
                "evidence": json.loads(row["evidence_json"]),
                "contradiction": json.loads(row["contradiction_json"]),
                "prev_event_hash": row["prev_event_hash"],
            }
            if _event_hash(body) != row["event_hash"]:
                return False
            previous = row["event_hash"]
        return True

    def _enqueue_work(
        self,
        *,
        work_key: str,
        created_at: str,
        due_at: str,
        kind: str,
        dispatch_class: str,
        priority: int,
        payload: dict[str, Any],
        source_event_key: str | None = None,
    ) -> bool:
        cursor = self.db.execute(
            """INSERT OR IGNORE INTO work_items (
                work_key,created_at,due_at,kind,dispatch_class,priority,status,
                payload_json,source_event_key
            ) VALUES (?,?,?,?,?,?,'QUEUED',?,?)""",
            (
                work_key,
                created_at,
                due_at,
                kind,
                dispatch_class,
                priority,
                canonical_json(payload),
                source_event_key,
            ),
        )
        return cursor.rowcount == 1

    def _window_key(self, event_class: str, now: datetime) -> str:
        local = self._local(now)
        if event_class == "ORDINARY_REVIEW":
            bucket = (local.minute // 10) * 10
            return f"{local:%Y-%m-%dT%H}:{bucket:02d}"
        if event_class == "DEEP_SYNTHESIS":
            return local.strftime("%Y-%m-%dT%H")
        if event_class in {"PORTFOLIO_REVIEW", "SCIENTIFIC_COMPATIBILITY"}:
            return local.strftime("%Y-%m-%d")
        if event_class == "FULL_CORPUS_AUDIT":
            return self.week_id(now)
        if event_class == "ARCHITECTURE_REVIEW":
            return local.strftime("%Y-%m")
        raise KeyError(event_class)

    def ensure_scheduled_work(self, now: datetime | None = None) -> list[str]:
        now = now or _utc_now()
        created_at = _iso(now)
        created: list[str] = []
        scheduled = (
            "DEEP_SYNTHESIS",
            "PORTFOLIO_REVIEW",
            "SCIENTIFIC_COMPATIBILITY",
            "FULL_CORPUS_AUDIT",
            "ARCHITECTURE_REVIEW",
        )
        if self.next_conversation(now) is not None:
            scheduled = ("ORDINARY_REVIEW",) + scheduled
        for event_class in scheduled:
            policy = self._policy(event_class)
            window = self._window_key(event_class, now)
            work_key = f"scheduled:{event_class}:{window}"
            payload: dict[str, Any] = {"event_class": event_class, "window": window}
            if event_class == "ORDINARY_REVIEW":
                payload["conversation_key"] = self.next_conversation(now)["conversation_key"]
            if self._enqueue_work(
                work_key=work_key,
                created_at=created_at,
                due_at=created_at,
                kind=event_class,
                dispatch_class=str(policy["dispatch_class"]),
                priority=int(policy["priority"]),
                payload=payload,
            ):
                created.append(work_key)
        self.db.commit()
        return created

    def due_work(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or _utc_now()
        rows = self.db.execute(
            """SELECT * FROM work_items
            WHERE status='QUEUED' AND due_at <= ?
            ORDER BY priority DESC, due_at ASC, work_key ASC""",
            (_iso(now),),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def claim_work(
        self,
        work_key: str,
        *,
        claimer: str,
        lease_seconds: int = 300,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        now = now or _utc_now()
        now_iso = _iso(now)
        lease_until = _iso(now + timedelta(seconds=lease_seconds))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT * FROM work_items WHERE work_key=?", (work_key,)
            ).fetchone()
            if row is None:
                self.db.rollback()
                return None
            claimable = row["status"] == "QUEUED" or (
                row["status"] == "RUNNING"
                and row["lease_until"]
                and _parse_iso(row["lease_until"]) <= now.astimezone(UTC)
            )
            if not claimable or _parse_iso(row["due_at"]) > now.astimezone(UTC):
                self.db.rollback()
                return None
            self.db.execute(
                """UPDATE work_items SET status='RUNNING', claimed_by=?, lease_until=?
                WHERE work_key=?""",
                (claimer, lease_until, work_key),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        claimed = self.db.execute(
            "SELECT * FROM work_items WHERE work_key=?", (work_key,)
        ).fetchone()
        item = dict(claimed)
        item["payload"] = json.loads(item.pop("payload_json"))
        item["claimed_at"] = now_iso
        return item

    def complete_work(
        self,
        work_key: str,
        *,
        result: dict[str, Any],
        now: datetime | None = None,
    ) -> None:
        now = now or _utc_now()
        completed_at = _iso(now)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT source_event_key,status FROM work_items WHERE work_key=?", (work_key,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown work item: {work_key}")
            if row["status"] == "COMPLETE":
                self.db.commit()
                return
            self.db.execute(
                """UPDATE work_items SET status='COMPLETE', completed_at=?, result_json=?,
                lease_until=NULL WHERE work_key=?""",
                (completed_at, canonical_json(result), work_key),
            )
            if row["source_event_key"]:
                self.db.execute(
                    """INSERT INTO event_processing(event_key,status,processed_at,result_json)
                    VALUES (?,'PROCESSED',?,?)
                    ON CONFLICT(event_key) DO UPDATE SET status='PROCESSED',
                    processed_at=excluded.processed_at,result_json=excluded.result_json""",
                    (row["source_event_key"], completed_at, canonical_json(result)),
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def cycle(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or _utc_now()
        created = self.ensure_scheduled_work(now)
        coverage = self.coverage(now)
        due = self.due_work(now)
        chain_valid = self.verify_event_chain()
        local = self._local(now)
        body = {
            "run_at": _iso(now),
            "timezone": self.timezone_name,
            "local_time": local.isoformat(),
            "coverage": coverage,
            "new_work_keys": created,
            "due_work": [
                {
                    "work_key": item["work_key"],
                    "kind": item["kind"],
                    "dispatch_class": item["dispatch_class"],
                    "priority": item["priority"],
                    "payload": item["payload"],
                }
                for item in due
            ],
            "event_chain_valid": chain_valid,
        }
        digest = sha256_json(body)
        cycle_key = f"cycle:{digest[:32]}"
        self.db.execute(
            """INSERT OR IGNORE INTO controller_cycles (
                cycle_key,run_at,local_window,coverage_json,due_work_json,
                event_chain_valid,cycle_hash
            ) VALUES (?,?,?,?,?,?,?)""",
            (
                cycle_key,
                body["run_at"],
                local.strftime("%Y-%m-%dT%H:%M"),
                canonical_json(coverage),
                canonical_json(body["due_work"]),
                int(chain_valid),
                digest,
            ),
        )
        self.db.commit()
        return {"cycle_key": cycle_key, **body, "cycle_hash": digest}

    def status(self, now: datetime | None = None) -> dict[str, Any]:
        counts = {}
        for table in (
            "change_events",
            "source_snapshots",
            "conversations",
            "conversation_reviews",
            "work_items",
            "controller_cycles",
        ):
            counts[table] = int(self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        pending = int(
            self.db.execute(
                "SELECT COUNT(*) FROM work_items WHERE status IN ('QUEUED','RUNNING')"
            ).fetchone()[0]
        )
        return {
            "path": str(self.path),
            "timezone": self.timezone_name,
            "event_chain_valid": self.verify_event_chain(),
            "coverage": self.coverage(now),
            "counts": counts,
            "pending_work": pending,
        }

    def run_forever(self, *, poll_seconds: float = 10.0) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        while True:
            cycle = self.cycle()
            if cycle["new_work_keys"] or cycle["due_work"]:
                print(canonical_json(cycle), flush=True)
            time.sleep(poll_seconds)
