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


class TheoryBranchStatus(StrEnum):
    ACTIVE_HYPOTHESIS = "ACTIVE_HYPOTHESIS"
    EMPIRICAL_LIMIT = "EMPIRICAL_LIMIT"
    EFFECTIVE_DESCRIPTION = "EFFECTIVE_DESCRIPTION"
    PHENOMENOLOGICAL_INTERFACE = "PHENOMENOLOGICAL_INTERFACE"
    DERIVED_LIMIT = "DERIVED_LIMIT"
    INCOMPATIBLE_BRANCH = "INCOMPATIBLE_BRANCH"
    REJECTED = "REJECTED"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class TheoryBranch:
    branch_id: str
    mathematical_definition: str
    assumptions: tuple[str, ...]
    parameters: Json
    observable_map: Json
    implementation_identity: str
    falsification_criteria: tuple[str, ...]
    status: TheoryBranchStatus = TheoryBranchStatus.ACTIVE_HYPOTHESIS
    parent_branch_id: str | None = None
    metadata: Json = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    @property
    def sha256(self) -> str:
        return _sha256(asdict(self))


@dataclass(frozen=True)
class ExperimentEvidence:
    experiment_id: str
    branch_sha256: str
    implementation_sha256: str
    inputs_sha256: str
    result: Json
    verification: Json
    falsified: bool
    verifier_independent: bool
    recorded_at: str = field(default_factory=_now)

    @property
    def sha256(self) -> str:
        return _sha256(asdict(self))


class ScientificBranchLedger:
    """Durable SDOS branch/evidence ledger that preserves incompatible and failed branches."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS branches (
                branch_id TEXT PRIMARY KEY,
                branch_sha256 TEXT NOT NULL UNIQUE,
                branch_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                branch_id TEXT NOT NULL,
                evidence_sha256 TEXT NOT NULL UNIQUE,
                evidence_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS branch_history (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_id TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                evidence_sha256 TEXT,
                recorded_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def add_branch(self, branch: TheoryBranch) -> str:
        if not branch.branch_id.strip() or not branch.mathematical_definition.strip():
            raise ValueError("branch_id and mathematical_definition are required")
        if not branch.falsification_criteria:
            raise ValueError("every theory branch requires falsification criteria")
        existing = self.db.execute(
            "SELECT branch_sha256 FROM branches WHERE branch_id=?", (branch.branch_id,)
        ).fetchone()
        if existing is not None:
            if existing["branch_sha256"] == branch.sha256:
                return branch.branch_id
            raise ValueError("branch_id already identifies different immutable theory content")
        if branch.parent_branch_id is not None:
            parent = self.db.execute(
                "SELECT 1 FROM branches WHERE branch_id=?", (branch.parent_branch_id,)
            ).fetchone()
            if parent is None:
                raise KeyError(f"unknown parent branch: {branch.parent_branch_id}")
        self.db.execute(
            "INSERT INTO branches VALUES(?,?,?,?,?,?)",
            (
                branch.branch_id,
                branch.sha256,
                json.dumps(asdict(branch), sort_keys=True),
                branch.status.value,
                branch.created_at,
                branch.created_at,
            ),
        )
        self.db.execute(
            "INSERT INTO branch_history(branch_id,status,reason,evidence_sha256,recorded_at) "
            "VALUES(?,?,?,?,?)",
            (branch.branch_id, branch.status.value, "branch_created", None, _now()),
        )
        self.db.commit()
        return branch.branch_id

    def record_experiment(self, branch_id: str, evidence: ExperimentEvidence) -> str:
        row = self.db.execute(
            "SELECT branch_sha256,status FROM branches WHERE branch_id=?", (branch_id,)
        ).fetchone()
        if row is None:
            raise KeyError(branch_id)
        if evidence.branch_sha256 != row["branch_sha256"]:
            raise ValueError("experiment evidence is not bound to this branch identity")
        if not evidence.verifier_independent:
            raise ValueError("scientific evidence requires an independent verifier declaration")
        existing = self.db.execute(
            "SELECT evidence_sha256 FROM experiments WHERE experiment_id=?",
            (evidence.experiment_id,),
        ).fetchone()
        if existing is not None:
            if existing["evidence_sha256"] == evidence.sha256:
                return evidence.experiment_id
            raise ValueError("experiment_id already identifies different immutable evidence")
        self.db.execute(
            "INSERT INTO experiments VALUES(?,?,?,?,?)",
            (
                evidence.experiment_id,
                branch_id,
                evidence.sha256,
                json.dumps(asdict(evidence), sort_keys=True),
                evidence.recorded_at,
            ),
        )
        self.db.commit()
        return evidence.experiment_id

    def transition(
        self,
        branch_id: str,
        status: TheoryBranchStatus,
        *,
        reason: str,
        evidence_sha256: str | None = None,
    ) -> TheoryBranchStatus:
        row = self.db.execute(
            "SELECT status FROM branches WHERE branch_id=?", (branch_id,)
        ).fetchone()
        if row is None:
            raise KeyError(branch_id)
        if not reason.strip():
            raise ValueError("status transition requires a reason")
        if evidence_sha256 is not None:
            evidence = self.db.execute(
                "SELECT 1 FROM experiments WHERE branch_id=? AND evidence_sha256=?",
                (branch_id, evidence_sha256),
            ).fetchone()
            if evidence is None:
                raise ValueError("status evidence is not registered for this branch")
        self.db.execute(
            "UPDATE branches SET status=?,updated_at=? WHERE branch_id=?",
            (status.value, _now(), branch_id),
        )
        self.db.execute(
            "INSERT INTO branch_history(branch_id,status,reason,evidence_sha256,recorded_at) "
            "VALUES(?,?,?,?,?)",
            (branch_id, status.value, reason, evidence_sha256, _now()),
        )
        self.db.commit()
        return status

    def classify_from_evidence(self, branch_id: str, experiment_id: str) -> TheoryBranchStatus:
        row = self.db.execute(
            "SELECT evidence_json FROM experiments WHERE experiment_id=? AND branch_id=?",
            (experiment_id, branch_id),
        ).fetchone()
        if row is None:
            raise KeyError(experiment_id)
        evidence = ExperimentEvidence(**json.loads(row["evidence_json"]))
        if evidence.falsified:
            target = TheoryBranchStatus.REJECTED
            reason = "registered experiment satisfied falsification condition"
        elif bool(evidence.verification.get("passed")):
            target = TheoryBranchStatus.REVIEW
            reason = "verified experiment retained branch for scientific review"
        else:
            target = TheoryBranchStatus.INCOMPATIBLE_BRANCH
            reason = "experiment verification did not support the branch implementation"
        return self.transition(
            branch_id,
            target,
            reason=reason,
            evidence_sha256=evidence.sha256,
        )

    def branch(self, branch_id: str) -> Json:
        row = self.db.execute("SELECT * FROM branches WHERE branch_id=?", (branch_id,)).fetchone()
        if row is None:
            raise KeyError(branch_id)
        body = json.loads(row["branch_json"])
        body["current_status"] = row["status"]
        body["branch_sha256"] = row["branch_sha256"]
        return body

    def history(self, branch_id: str) -> list[Json]:
        rows = self.db.execute(
            "SELECT * FROM branch_history WHERE branch_id=? ORDER BY sequence", (branch_id,)
        ).fetchall()
        return [dict(row) for row in rows]
