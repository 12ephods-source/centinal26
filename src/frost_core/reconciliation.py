from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class ReconciliationState(StrEnum):
    PENDING = "PENDING"
    APPLIED = "APPLIED"
    DIVERGED = "DIVERGED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ControlPlaneSnapshot:
    adapter_id: str
    object_type: str
    object_id: str
    desired: Json
    observed: Json
    immutable_evidence_identity: str
    observed_at: str = field(default_factory=_now)

    @property
    def identity(self) -> str:
        return _sha256(asdict(self))


@dataclass(frozen=True)
class ReconciliationDecision:
    snapshot_identity: str
    state: ReconciliationState
    patch: Json
    reason: str
    evidence_identity: str


class ReconciliationLedger:
    """Repeatable control-plane reconciliation without making the control plane canonical.

    The immutable execution evidence identity is mandatory. The adapter may mirror current
    state into Base44 or another UI/queue system, but it cannot replace the evidence object
    used to establish what happened.
    """

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_identity TEXT PRIMARY KEY,
                snapshot_json TEXT NOT NULL,
                state TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS mirrors (
                adapter_id TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                last_snapshot_identity TEXT NOT NULL,
                last_observed_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(adapter_id,object_type,object_id)
            );
            """
        )
        self.db.commit()

    def evaluate(self, snapshot: ControlPlaneSnapshot) -> ReconciliationDecision:
        if not snapshot.immutable_evidence_identity.strip():
            raise ValueError("immutable execution evidence identity is required")
        if not snapshot.adapter_id.strip() or not snapshot.object_id.strip():
            raise ValueError("adapter_id and object_id are required")
        patch = self._diff(snapshot.observed, snapshot.desired)
        state = ReconciliationState.APPLIED if not patch else ReconciliationState.PENDING
        reason = "already converged" if not patch else "control-plane mirror requires update"
        decision = ReconciliationDecision(
            snapshot_identity=snapshot.identity,
            state=state,
            patch=patch,
            reason=reason,
            evidence_identity=snapshot.immutable_evidence_identity,
        )
        self.db.execute(
            "INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?,?)",
            (
                snapshot.identity,
                json.dumps(asdict(snapshot), sort_keys=True),
                state.value,
                json.dumps(asdict(decision), sort_keys=True),
                _now(),
            ),
        )
        self.db.commit()
        return decision

    def mark_applied(
        self, snapshot: ControlPlaneSnapshot, observed_after: Json
    ) -> ReconciliationDecision:
        patch = self._diff(observed_after, snapshot.desired)
        if patch:
            state = ReconciliationState.DIVERGED
            reason = "post-write readback diverged from desired mirror state"
        else:
            state = ReconciliationState.APPLIED
            reason = "post-write readback matches desired mirror state"
        decision = ReconciliationDecision(
            snapshot_identity=snapshot.identity,
            state=state,
            patch=patch,
            reason=reason,
            evidence_identity=snapshot.immutable_evidence_identity,
        )
        self.db.execute(
            "UPDATE snapshots SET state=?,decision_json=?,recorded_at=? WHERE snapshot_identity=?",
            (state.value, json.dumps(asdict(decision), sort_keys=True), _now(), snapshot.identity),
        )
        self.db.execute(
            """
            INSERT INTO mirrors VALUES(?,?,?,?,?,?)
            ON CONFLICT(adapter_id,object_type,object_id) DO UPDATE SET
              last_snapshot_identity=excluded.last_snapshot_identity,
              last_observed_json=excluded.last_observed_json,
              updated_at=excluded.updated_at
            """,
            (
                snapshot.adapter_id,
                snapshot.object_type,
                snapshot.object_id,
                snapshot.identity,
                json.dumps(observed_after, sort_keys=True),
                _now(),
            ),
        )
        self.db.commit()
        return decision

    def last_mirror(self, adapter_id: str, object_type: str, object_id: str) -> Json | None:
        row = self.db.execute(
            """
            SELECT * FROM mirrors WHERE adapter_id=? AND object_type=? AND object_id=?
            """,
            (adapter_id, object_type, object_id),
        ).fetchone()
        return None if row is None else dict(row)

    @classmethod
    def _diff(cls, observed: Any, desired: Any) -> Json:
        if isinstance(desired, dict) and isinstance(observed, dict):
            patch: Json = {}
            for key, expected in desired.items():
                if key not in observed:
                    patch[key] = {"op": "set", "value": expected}
                    continue
                actual = observed[key]
                if isinstance(expected, dict) and isinstance(actual, dict):
                    nested = cls._diff(actual, expected)
                    if nested:
                        patch[key] = nested
                elif actual != expected:
                    patch[key] = {"op": "set", "value": expected, "observed": actual}
            return patch
        return {} if observed == desired else {"$": {"op": "set", "value": desired}}
