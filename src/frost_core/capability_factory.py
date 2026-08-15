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


class CapabilityStage(StrEnum):
    DISCOVERED = "DISCOVERED"
    WRAPPED = "WRAPPED"
    BUILDABLE = "BUILDABLE"
    TESTED = "TESTED"
    DEPLOYED = "DEPLOYED"
    REACHABLE = "REACHABLE"
    CHATGPT_CALLABLE_VERIFIED = "CHATGPT_CALLABLE_VERIFIED"
    PROMOTED = "PROMOTED"
    BLOCKED = "BLOCKED"
    QUARANTINED = "QUARANTINED"
    DEMOTED = "DEMOTED"


ORDERED_STAGES = (
    CapabilityStage.DISCOVERED,
    CapabilityStage.WRAPPED,
    CapabilityStage.BUILDABLE,
    CapabilityStage.TESTED,
    CapabilityStage.DEPLOYED,
    CapabilityStage.REACHABLE,
    CapabilityStage.CHATGPT_CALLABLE_VERIFIED,
    CapabilityStage.PROMOTED,
)


REQUIRED_PROMOTION_GATES = (
    "provider_deployment_exists",
    "health_200",
    "source_hash_match",
    "capabilities_contract",
    "semantic_invoke",
    "guardian_denial",
    "independent_verification",
    "provenance_receipt",
)


@dataclass(frozen=True)
class CapabilityCandidate:
    capability_id: str
    operation: str
    source_identity: str
    adapter_identity: str
    risk_class: str
    provider_id: str
    schema_identity: str
    metadata: Json = field(default_factory=dict)

    @property
    def identity(self) -> str:
        return _sha256(asdict(self))


@dataclass(frozen=True)
class GateEvidence:
    gate: str
    passed: bool
    evidence: Json
    recorded_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class PromotionDecision:
    capability_id: str
    previous_stage: CapabilityStage
    new_stage: CapabilityStage
    reason: str
    failed_gates: tuple[str, ...]
    evidence_hash: str


class CapabilityFactoryLedger:
    """Durable, fail-closed capability promotion ledger.

    Discovery is inventory only. It never grants execution authority. Promotion requires
    all mandatory gates and a stable candidate identity. A source/adapter/schema identity
    change invalidates prior gate evidence instead of inheriting trust across new bytes.
    """

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                capability_id TEXT PRIMARY KEY,
                candidate_identity TEXT NOT NULL,
                candidate_json TEXT NOT NULL,
                stage TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS gates (
                capability_id TEXT NOT NULL,
                candidate_identity TEXT NOT NULL,
                gate TEXT NOT NULL,
                passed INTEGER NOT NULL,
                evidence_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                PRIMARY KEY(capability_id,candidate_identity,gate)
            );
            CREATE TABLE IF NOT EXISTS decisions (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                capability_id TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def discover(self, candidate: CapabilityCandidate) -> CapabilityStage:
        if not candidate.capability_id.strip() or not candidate.operation.strip():
            raise ValueError("capability_id and operation are required")
        if candidate.risk_class.lower() in {"shell", "arbitrary_shell", "remote_shell"}:
            raise ValueError("unrestricted shell capabilities are not admissible")
        row = self.db.execute(
            "SELECT candidate_identity,stage FROM candidates WHERE capability_id=?",
            (candidate.capability_id,),
        ).fetchone()
        if row is None:
            stage = CapabilityStage.DISCOVERED
        elif row["candidate_identity"] == candidate.identity:
            return CapabilityStage(row["stage"])
        else:
            stage = CapabilityStage.DISCOVERED
        self.db.execute(
            """
            INSERT INTO candidates VALUES(?,?,?,?,?)
            ON CONFLICT(capability_id) DO UPDATE SET
              candidate_identity=excluded.candidate_identity,
              candidate_json=excluded.candidate_json,
              stage=excluded.stage,
              updated_at=excluded.updated_at
            """,
            (
                candidate.capability_id,
                candidate.identity,
                json.dumps(asdict(candidate), sort_keys=True),
                stage.value,
                _now(),
            ),
        )
        self.db.commit()
        return stage

    def advance_structural(self, capability_id: str, target: CapabilityStage) -> CapabilityStage:
        if target not in ORDERED_STAGES[:5]:
            raise ValueError("structural advancement is limited through DEPLOYED")
        row = self._candidate_row(capability_id)
        current = CapabilityStage(row["stage"])
        current_index = ORDERED_STAGES.index(current)
        target_index = ORDERED_STAGES.index(target)
        if target_index > current_index + 1:
            raise ValueError("capability stages may not be skipped")
        if target_index <= current_index:
            return current
        self._set_stage(capability_id, target)
        return target

    def record_gate(self, capability_id: str, evidence: GateEvidence) -> None:
        if evidence.gate not in REQUIRED_PROMOTION_GATES:
            raise ValueError(f"unknown promotion gate: {evidence.gate}")
        row = self._candidate_row(capability_id)
        self.db.execute(
            """
            INSERT INTO gates VALUES(?,?,?,?,?,?)
            ON CONFLICT(capability_id,candidate_identity,gate) DO UPDATE SET
              passed=excluded.passed,
              evidence_json=excluded.evidence_json,
              recorded_at=excluded.recorded_at
            """,
            (
                capability_id,
                row["candidate_identity"],
                evidence.gate,
                int(evidence.passed),
                json.dumps(evidence.evidence, sort_keys=True),
                evidence.recorded_at,
            ),
        )
        self.db.commit()

    def evaluate(self, capability_id: str) -> PromotionDecision:
        row = self._candidate_row(capability_id)
        previous = CapabilityStage(row["stage"])
        identity = str(row["candidate_identity"])
        gates = self.db.execute(
            "SELECT gate,passed,evidence_json FROM gates "
            "WHERE capability_id=? AND candidate_identity=?",
            (capability_id, identity),
        ).fetchall()
        observed = {str(gate["gate"]): bool(gate["passed"]) for gate in gates}
        failed = tuple(
            gate for gate in REQUIRED_PROMOTION_GATES if not observed.get(gate, False)
        )
        evidence_payload = {
            "candidate_identity": identity,
            "gates": {
                str(gate["gate"]): {
                    "passed": bool(gate["passed"]),
                    "evidence": json.loads(gate["evidence_json"]),
                }
                for gate in gates
            },
        }
        evidence_hash = _sha256(evidence_payload)

        if not failed:
            new_stage = CapabilityStage.PROMOTED
            reason = "all mandatory promotion gates passed"
        elif previous == CapabilityStage.PROMOTED:
            new_stage = CapabilityStage.DEMOTED
            reason = "promoted capability regressed a mandatory gate"
        elif observed.get("source_hash_match") is False and "source_hash_match" in observed:
            new_stage = CapabilityStage.QUARANTINED
            reason = "source identity mismatch"
        elif observed.get("provider_deployment_exists") is False:
            new_stage = CapabilityStage.BLOCKED
            reason = "execution provider unavailable"
        elif observed.get("health_200") and observed.get("provider_deployment_exists"):
            new_stage = CapabilityStage.REACHABLE
            reason = "provider reachable; semantic promotion gates incomplete"
        else:
            new_stage = previous
            reason = "promotion gates incomplete"

        decision = PromotionDecision(
            capability_id=capability_id,
            previous_stage=previous,
            new_stage=new_stage,
            reason=reason,
            failed_gates=failed,
            evidence_hash=evidence_hash,
        )
        self._set_stage(capability_id, new_stage)
        self.db.execute(
            "INSERT INTO decisions(capability_id,decision_json,recorded_at) VALUES(?,?,?)",
            (capability_id, json.dumps(asdict(decision), sort_keys=True), _now()),
        )
        self.db.commit()
        return decision

    def status(self, capability_id: str) -> Json:
        row = self._candidate_row(capability_id)
        return {
            "capability_id": capability_id,
            "candidate_identity": row["candidate_identity"],
            "stage": row["stage"],
            "candidate": json.loads(row["candidate_json"]),
        }

    def _candidate_row(self, capability_id: str) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM candidates WHERE capability_id=?", (capability_id,)
        ).fetchone()
        if row is None:
            raise KeyError(capability_id)
        return row

    def _set_stage(self, capability_id: str, stage: CapabilityStage) -> None:
        self.db.execute(
            "UPDATE candidates SET stage=?,updated_at=? WHERE capability_id=?",
            (stage.value, _now(), capability_id),
        )
        self.db.commit()
