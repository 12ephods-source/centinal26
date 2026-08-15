from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64
ROLES = ("GOVERNOR", "BUILDER", "JUDGE", "SRE", "EVOLUTION")
PRIORITIES = ("P0", "P1", "P2", "P3", "P4")
PRIORITY_BASE = {"P0": 500.0, "P1": 400.0, "P2": 300.0, "P3": 200.0, "P4": 100.0}
SUCCESS_STATES = {
    "VERIFIED", "OPERATIONAL", "PHYSICAL_VALIDATED", "READY_FOR_GA_PROMOTION",
    "GA", "SUPERSEDED", "RETIRED",
}

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS fleet_contracts (
    contract_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    problem_statement TEXT NOT NULL,
    source_basis_json TEXT NOT NULL,
    priority TEXT NOT NULL,
    rank_score REAL NOT NULL,
    ranking_json TEXT NOT NULL,
    expected_outcome TEXT NOT NULL,
    success_criteria_json TEXT NOT NULL,
    allowed_scope_json TEXT NOT NULL,
    prohibited_scope_json TEXT NOT NULL,
    dependencies_json TEXT NOT NULL,
    assigned_role TEXT NOT NULL,
    verification_requirements_json TEXT NOT NULL,
    rollback_plan_json TEXT NOT NULL,
    resource_budget_json TEXT NOT NULL,
    retry_budget INTEGER NOT NULL,
    current_head TEXT NOT NULL,
    subsystem TEXT NOT NULL,
    failure_criteria_json TEXT NOT NULL,
    next_review_condition TEXT NOT NULL,
    on_verified_role TEXT,
    contract_hash TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS fleet_contracts_no_update
BEFORE UPDATE ON fleet_contracts BEGIN
    SELECT RAISE(ABORT, 'fleet contracts are append-only');
END;
CREATE TRIGGER IF NOT EXISTS fleet_contracts_no_delete
BEFORE DELETE ON fleet_contracts BEGIN
    SELECT RAISE(ABORT, 'fleet contracts are append-only');
END;
CREATE TABLE IF NOT EXISTS fleet_contract_state (
    contract_id TEXT PRIMARY KEY REFERENCES fleet_contracts(contract_id),
    status TEXT NOT NULL,
    owner_role TEXT NOT NULL,
    claimed_by TEXT,
    lease_until TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    terminal_reason TEXT
);
CREATE TABLE IF NOT EXISTS fleet_results (
    result_id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES fleet_contracts(contract_id),
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    result_hash TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS fleet_results_no_update
BEFORE UPDATE ON fleet_results BEGIN
    SELECT RAISE(ABORT, 'fleet results are append-only');
END;
CREATE TRIGGER IF NOT EXISTS fleet_results_no_delete
BEFORE DELETE ON fleet_results BEGIN
    SELECT RAISE(ABORT, 'fleet results are append-only');
END;
CREATE TABLE IF NOT EXISTS fleet_verdicts (
    verdict_id TEXT PRIMARY KEY,
    result_id TEXT NOT NULL UNIQUE REFERENCES fleet_results(result_id),
    contract_id TEXT NOT NULL REFERENCES fleet_contracts(contract_id),
    verdict TEXT NOT NULL,
    verifier TEXT NOT NULL,
    created_at TEXT NOT NULL,
    details_json TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    verdict_hash TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS fleet_verdicts_no_update
BEFORE UPDATE ON fleet_verdicts BEGIN
    SELECT RAISE(ABORT, 'fleet verdicts are append-only');
END;
CREATE TRIGGER IF NOT EXISTS fleet_verdicts_no_delete
BEFORE DELETE ON fleet_verdicts BEGIN
    SELECT RAISE(ABORT, 'fleet verdicts are append-only');
END;
CREATE TABLE IF NOT EXISTS fleet_handoffs (
    handoff_id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES fleet_contracts(contract_id),
    source_result_id TEXT REFERENCES fleet_results(result_id),
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    handoff_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS fleet_handoff_state (
    handoff_id TEXT PRIMARY KEY REFERENCES fleet_handoffs(handoff_id),
    status TEXT NOT NULL,
    claimed_at TEXT,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS fleet_error_events (
    error_id TEXT PRIMARY KEY,
    subsystem TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    recovered INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    details_json TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS fleet_metric_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    captured_at TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    metrics_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS fleet_event_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_event_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS fleet_event_log_no_update
BEFORE UPDATE ON fleet_event_log BEGIN
    SELECT RAISE(ABORT, 'fleet event log is append-only');
END;
CREATE TRIGGER IF NOT EXISTS fleet_event_log_no_delete
BEFORE DELETE ON fleet_event_log BEGIN
    SELECT RAISE(ABORT, 'fleet event log is append-only');
END;
"""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def rank_contract(priority: str, ranking: dict[str, float] | None = None) -> float:
    if priority not in PRIORITY_BASE:
        raise ValueError(f"invalid priority: {priority}")
    factors = {
        "downstream_leverage": 0.0, "user_impact": 0.0, "dependency_unblocking": 0.0,
        "uncertainty_reduction": 0.0, "information_gain": 0.0, "success_probability": 0.5,
        "verification_value": 0.0, "execution_readiness": 0.0, "remaining_cost": 0.5,
        "maintenance_burden": 0.0, "rollback_cost": 0.0, "risk": 0.0,
    }
    for key, value in (ranking or {}).items():
        if key not in factors:
            raise ValueError(f"unknown ranking factor: {key}")
        numeric = float(value)
        if not 0.0 <= numeric <= 1.0:
            raise ValueError(f"ranking factor {key} must be in [0, 1]")
        factors[key] = numeric
    positive = (
        32 * factors["downstream_leverage"] + 28 * factors["user_impact"]
        + 32 * factors["dependency_unblocking"] + 18 * factors["uncertainty_reduction"]
        + 18 * factors["information_gain"] + 16 * factors["success_probability"]
        + 16 * factors["verification_value"] + 18 * factors["execution_readiness"]
    )
    negative = (
        18 * factors["remaining_cost"] + 14 * factors["maintenance_burden"]
        + 18 * factors["rollback_cost"] + 30 * factors["risk"]
    )
    return round(PRIORITY_BASE[priority] + positive - negative, 6)


class FleetController:
    """Durable coordination protocol for the five-role Frost automation fleet.

    It coordinates contracts, evidence, verification, handoffs and operational error budgets.
    It deliberately does not grant external execution authority.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def _append_event(self, event_type: str, entity_id: str, payload: dict[str, Any], *, now: datetime) -> str:
        latest = self.db.execute("SELECT event_hash FROM fleet_event_log ORDER BY seq DESC LIMIT 1").fetchone()
        previous = latest["event_hash"] if latest else GENESIS_HASH
        body = {
            "occurred_at": _iso(now), "event_type": event_type, "entity_id": entity_id,
            "payload": payload, "prev_event_hash": previous,
        }
        digest = sha256_json(body)
        event_id = f"fleet:{event_type.lower()}:{digest[:32]}"
        self.db.execute(
            """INSERT INTO fleet_event_log (
                event_id,occurred_at,event_type,entity_id,payload_json,prev_event_hash,event_hash
            ) VALUES (?,?,?,?,?,?,?)""",
            (event_id, body["occurred_at"], event_type, entity_id, canonical_json(payload), previous, digest),
        )
        return digest

    def verify_event_chain(self) -> bool:
        previous = GENESIS_HASH
        for row in self.db.execute("SELECT * FROM fleet_event_log ORDER BY seq"):
            if row["prev_event_hash"] != previous:
                return False
            body = {
                "occurred_at": row["occurred_at"], "event_type": row["event_type"],
                "entity_id": row["entity_id"], "payload": json.loads(row["payload_json"]),
                "prev_event_hash": row["prev_event_hash"],
            }
            if sha256_json(body) != row["event_hash"]:
                return False
            previous = row["event_hash"]
        return True

    def create_contract(
        self, *, idempotency_key: str, problem_statement: str, source_basis: dict[str, Any],
        priority: str, expected_outcome: str, success_criteria: list[str], allowed_scope: list[str],
        prohibited_scope: list[str], dependencies: list[str], assigned_role: str,
        verification_requirements: list[str], rollback_plan: dict[str, Any],
        resource_budget: dict[str, Any], retry_budget: int, current_head: str, subsystem: str,
        failure_criteria: list[str], next_review_condition: str,
        ranking: dict[str, float] | None = None, on_verified_role: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if priority not in PRIORITIES:
            raise ValueError(f"invalid priority: {priority}")
        if assigned_role not in ROLES:
            raise ValueError(f"invalid role: {assigned_role}")
        if on_verified_role is not None and on_verified_role not in ROLES:
            raise ValueError(f"invalid on_verified_role: {on_verified_role}")
        if retry_budget < 0:
            raise ValueError("retry_budget must be non-negative")
        if not idempotency_key or not problem_statement or not subsystem:
            raise ValueError("idempotency_key, problem_statement, and subsystem are required")
        existing = self.db.execute(
            """SELECT c.*,s.status,s.owner_role,s.attempt_count
            FROM fleet_contracts c JOIN fleet_contract_state s USING(contract_id)
            WHERE c.idempotency_key=?""", (idempotency_key,),
        ).fetchone()
        if existing:
            result = dict(existing)
            result["created"] = False
            return result
        now = now or _utc_now()
        created_at = _iso(now)
        ranking = dict(ranking or {})
        score = rank_contract(priority, ranking)
        body = {
            "idempotency_key": idempotency_key, "created_at": created_at,
            "problem_statement": problem_statement, "source_basis": source_basis,
            "priority": priority, "rank_score": score, "ranking": ranking,
            "expected_outcome": expected_outcome, "success_criteria": success_criteria,
            "allowed_scope": allowed_scope, "prohibited_scope": prohibited_scope,
            "dependencies": dependencies, "assigned_role": assigned_role,
            "verification_requirements": verification_requirements, "rollback_plan": rollback_plan,
            "resource_budget": resource_budget, "retry_budget": retry_budget,
            "current_head": current_head, "subsystem": subsystem,
            "failure_criteria": failure_criteria, "next_review_condition": next_review_condition,
            "on_verified_role": on_verified_role,
        }
        contract_hash = sha256_json(body)
        contract_id = f"contract:{contract_hash[:32]}"
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                """INSERT INTO fleet_contracts (
                    contract_id,idempotency_key,created_at,problem_statement,source_basis_json,
                    priority,rank_score,ranking_json,expected_outcome,success_criteria_json,
                    allowed_scope_json,prohibited_scope_json,dependencies_json,assigned_role,
                    verification_requirements_json,rollback_plan_json,resource_budget_json,
                    retry_budget,current_head,subsystem,failure_criteria_json,next_review_condition,
                    on_verified_role,contract_hash
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (contract_id,idempotency_key,created_at,problem_statement,canonical_json(source_basis),
                 priority,score,canonical_json(ranking),expected_outcome,canonical_json(success_criteria),
                 canonical_json(allowed_scope),canonical_json(prohibited_scope),canonical_json(dependencies),
                 assigned_role,canonical_json(verification_requirements),canonical_json(rollback_plan),
                 canonical_json(resource_budget),retry_budget,current_head,subsystem,
                 canonical_json(failure_criteria),next_review_condition,on_verified_role,contract_hash),
            )
            self.db.execute(
                "INSERT INTO fleet_contract_state (contract_id,status,owner_role,updated_at) VALUES (?,'READY',?,?)",
                (contract_id, assigned_role, created_at),
            )
            self._append_event("CONTRACT_CREATED", contract_id, {
                "priority": priority, "rank_score": score, "assigned_role": assigned_role,
                "subsystem": subsystem, "contract_hash": contract_hash,
            }, now=now)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"contract_id": contract_id, "contract_hash": contract_hash, "rank_score": score,
                "status": "READY", "owner_role": assigned_role, "created": True}

    def _dependencies_satisfied(self, dependencies_json: str) -> bool:
        for dependency in json.loads(dependencies_json):
            row = self.db.execute("SELECT status FROM fleet_contract_state WHERE contract_id=?", (dependency,)).fetchone()
            if row is None or row["status"] not in SUCCESS_STATES:
                return False
        return True

    def _error_budget(self, subsystem: str, *, now: datetime, hours: int = 24) -> dict[str, Any]:
        cutoff = _iso(now - timedelta(hours=hours))
        rows = self.db.execute(
            "SELECT event_type,severity,recovered FROM fleet_error_events WHERE subsystem=? AND occurred_at>=?",
            (subsystem, cutoff),
        ).fetchall()
        total = len(rows)
        unrecovered = sum(not bool(row["recovered"]) for row in rows)
        invariant = sum(row["event_type"] == "INVARIANT_VIOLATION" for row in rows)
        rollback = sum(row["event_type"] == "ROLLBACK" for row in rows)
        failure_rate = unrecovered / total if total else 0.0
        contracted = invariant > 0 or (total >= 4 and unrecovered >= 2 and failure_rate >= 0.25)
        return {"subsystem": subsystem, "window_hours": hours, "events": total,
                "unrecovered": unrecovered, "rollbacks": rollback,
                "invariant_violations": invariant, "failure_rate": failure_rate,
                "contracted": contracted}

    def error_budget(self, subsystem: str, *, now: datetime | None = None) -> dict[str, Any]:
        return self._error_budget(subsystem, now=now or _utc_now())

    def claim_next(self, role: str, *, claimer: str, lease_seconds: int = 600,
                   batch_limit: int = 1, now: datetime | None = None) -> list[dict[str, Any]]:
        if role not in ROLES:
            raise ValueError(f"invalid role: {role}")
        if lease_seconds < 1 or batch_limit < 1 or batch_limit > 3:
            raise ValueError("invalid lease_seconds or batch_limit")
        now = now or _utc_now()
        now_iso = _iso(now)
        rows = self.db.execute(
            """SELECT c.*,s.status,s.owner_role,s.claimed_by,s.lease_until,s.attempt_count
            FROM fleet_contracts c JOIN fleet_contract_state s USING(contract_id)
            WHERE s.owner_role=? AND (s.status='READY' OR
              (s.status='RUNNING' AND s.lease_until IS NOT NULL AND s.lease_until<=?))
            ORDER BY c.rank_score DESC,c.created_at ASC,c.contract_id ASC""", (role, now_iso),
        ).fetchall()
        claimed: list[dict[str, Any]] = []
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for row in rows:
                if len(claimed) >= batch_limit:
                    break
                if int(row["attempt_count"]) >= int(row["retry_budget"]) + 1:
                    self.db.execute(
                        """UPDATE fleet_contract_state SET status='FAILED_PRESERVED',updated_at=?,terminal_reason=?
                        WHERE contract_id=?""", (now_iso, "retry budget exhausted", row["contract_id"]),
                    )
                    self._append_event("CONTRACT_FAILED", row["contract_id"], {"reason": "retry budget exhausted"}, now=now)
                    continue
                if not self._dependencies_satisfied(row["dependencies_json"]):
                    continue
                budget = self._error_budget(row["subsystem"], now=now)
                if budget["contracted"] and role not in {"JUDGE", "SRE"}:
                    continue
                lease_until = _iso(now + timedelta(seconds=lease_seconds))
                self.db.execute(
                    """UPDATE fleet_contract_state SET status='RUNNING',claimed_by=?,lease_until=?,
                    attempt_count=attempt_count+1,updated_at=?,terminal_reason=NULL WHERE contract_id=?""",
                    (claimer, lease_until, now_iso, row["contract_id"]),
                )
                self._append_event("CONTRACT_CLAIMED", row["contract_id"],
                    {"role": role, "claimer": claimer, "lease_until": lease_until}, now=now)
                item = dict(row)
                item.update(status="RUNNING", claimed_by=claimer, lease_until=lease_until,
                            attempt_count=int(row["attempt_count"]) + 1)
                for key in ("source_basis_json","ranking_json","success_criteria_json","allowed_scope_json",
                            "prohibited_scope_json","dependencies_json","verification_requirements_json",
                            "rollback_plan_json","resource_budget_json","failure_criteria_json"):
                    item[key.removesuffix("_json")] = json.loads(item.pop(key))
                claimed.append(item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return claimed

    def _create_handoff(self, contract_id: str, *, source_result_id: str | None,
                        from_role: str, to_role: str, reason: str, now: datetime) -> str:
        body = {"contract_id": contract_id, "source_result_id": source_result_id,
                "from_role": from_role, "to_role": to_role, "reason": reason, "created_at": _iso(now)}
        digest = sha256_json(body)
        handoff_id = f"handoff:{digest[:32]}"
        self.db.execute(
            """INSERT OR IGNORE INTO fleet_handoffs
            (handoff_id,contract_id,source_result_id,from_role,to_role,reason,created_at,handoff_hash)
            VALUES (?,?,?,?,?,?,?,?)""",
            (handoff_id,contract_id,source_result_id,from_role,to_role,reason,body["created_at"],digest),
        )
        self.db.execute("INSERT OR IGNORE INTO fleet_handoff_state (handoff_id,status) VALUES (?,'PENDING')", (handoff_id,))
        self.db.execute(
            """UPDATE fleet_contract_state SET owner_role=?,status='READY',claimed_by=NULL,lease_until=NULL,updated_at=?
            WHERE contract_id=?""", (to_role, body["created_at"], contract_id),
        )
        self._append_event("HANDOFF_CREATED", handoff_id,
            {"contract_id": contract_id, "from_role": from_role, "to_role": to_role, "reason": reason}, now=now)
        return handoff_id

    def record_result(self, contract_id: str, *, role: str, status: str, payload: dict[str, Any],
                      evidence_hash: str = "", now: datetime | None = None) -> dict[str, Any]:
        if role not in ROLES:
            raise ValueError(f"invalid role: {role}")
        now = now or _utc_now()
        created_at = _iso(now)
        state = self.db.execute(
            """SELECT c.*,s.status state_status,s.owner_role FROM fleet_contracts c
            JOIN fleet_contract_state s USING(contract_id) WHERE c.contract_id=?""", (contract_id,),
        ).fetchone()
        if state is None:
            raise KeyError(f"unknown contract: {contract_id}")
        if state["owner_role"] != role and role != "JUDGE":
            raise ValueError(f"contract owned by {state['owner_role']}, not {role}")
        body = {"contract_id": contract_id, "role": role, "status": status,
                "created_at": created_at, "payload": payload, "evidence_hash": evidence_hash}
        result_hash = sha256_json(body)
        result_id = f"result:{result_hash[:32]}"
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "INSERT INTO fleet_results (result_id,contract_id,role,status,created_at,payload_json,evidence_hash,result_hash) VALUES (?,?,?,?,?,?,?,?)",
                (result_id,contract_id,role,status,created_at,canonical_json(payload),evidence_hash,result_hash),
            )
            if status in {"EXECUTED_AWAITING_VERIFICATION","CANDIDATE_PACKAGE_AWAITING_VERIFICATION","PHYSICAL_EVIDENCE_AWAITING_VERIFICATION"}:
                self._create_handoff(contract_id, source_result_id=result_id, from_role=role, to_role="JUDGE",
                                     reason="independent verification required", now=now)
            elif status in SUCCESS_STATES:
                self.db.execute(
                    "UPDATE fleet_contract_state SET status=?,claimed_by=NULL,lease_until=NULL,updated_at=?,terminal_reason=NULL WHERE contract_id=?",
                    (status, created_at, contract_id),
                )
            elif status in {"BLOCKED_EXTERNAL","FAILED_PRESERVED","CANCELLED"}:
                self.db.execute(
                    "UPDATE fleet_contract_state SET status=?,claimed_by=NULL,lease_until=NULL,updated_at=?,terminal_reason=? WHERE contract_id=?",
                    (status, created_at, payload.get("reason", status), contract_id),
                )
            else:
                self.db.execute(
                    "UPDATE fleet_contract_state SET status='READY',claimed_by=NULL,lease_until=NULL,updated_at=? WHERE contract_id=?",
                    (created_at, contract_id),
                )
            self._append_event("RESULT_RECORDED", result_id,
                {"contract_id": contract_id, "role": role, "status": status, "result_hash": result_hash}, now=now)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"result_id": result_id, "result_hash": result_hash, "status": status}

    def pending_verification(self, *, limit: int = 3) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """SELECT r.*,c.problem_statement,c.priority,c.verification_requirements_json,c.contract_hash
            FROM fleet_results r JOIN fleet_contracts c USING(contract_id)
            LEFT JOIN fleet_verdicts v ON v.result_id=r.result_id WHERE v.result_id IS NULL AND r.status IN
            ('EXECUTED_AWAITING_VERIFICATION','CANDIDATE_PACKAGE_AWAITING_VERIFICATION','PHYSICAL_EVIDENCE_AWAITING_VERIFICATION')
            ORDER BY c.rank_score DESC,r.created_at ASC LIMIT ?""", (limit,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            item["verification_requirements"] = json.loads(item.pop("verification_requirements_json"))
            result.append(item)
        return result

    def record_verdict(self, result_id: str, *, verdict: str, verifier: str, details: dict[str, Any],
                       evidence_hash: str = "", now: datetime | None = None) -> dict[str, Any]:
        if verdict not in {"VERIFIED","VERIFICATION_FAILED","INCONCLUSIVE","BLOCKED_EXTERNAL"}:
            raise ValueError(f"invalid verdict: {verdict}")
        row = self.db.execute(
            """SELECT r.*,c.assigned_role,c.on_verified_role FROM fleet_results r
            JOIN fleet_contracts c USING(contract_id) WHERE r.result_id=?""", (result_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown result: {result_id}")
        existing = self.db.execute("SELECT * FROM fleet_verdicts WHERE result_id=?", (result_id,)).fetchone()
        if existing:
            return {**dict(existing), "created": False}
        now = now or _utc_now()
        created_at = _iso(now)
        body = {"result_id": result_id, "contract_id": row["contract_id"], "verdict": verdict,
                "verifier": verifier, "created_at": created_at, "details": details, "evidence_hash": evidence_hash}
        verdict_hash = sha256_json(body)
        verdict_id = f"verdict:{verdict_hash[:32]}"
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "INSERT INTO fleet_verdicts (verdict_id,result_id,contract_id,verdict,verifier,created_at,details_json,evidence_hash,verdict_hash) VALUES (?,?,?,?,?,?,?,?,?)",
                (verdict_id,result_id,row["contract_id"],verdict,verifier,created_at,canonical_json(details),evidence_hash,verdict_hash),
            )
            if verdict == "VERIFIED":
                next_role = row["on_verified_role"]
                if next_role:
                    self._create_handoff(row["contract_id"], source_result_id=result_id, from_role="JUDGE",
                                         to_role=next_role, reason="verified result eligible for next operational stage", now=now)
                else:
                    self.db.execute(
                        "UPDATE fleet_contract_state SET status='VERIFIED',owner_role='JUDGE',claimed_by=NULL,lease_until=NULL,updated_at=?,terminal_reason=NULL WHERE contract_id=?",
                        (created_at, row["contract_id"]),
                    )
            elif verdict == "VERIFICATION_FAILED":
                self._create_handoff(row["contract_id"], source_result_id=result_id, from_role="JUDGE",
                                     to_role=row["assigned_role"], reason="verification failed; corrective work required", now=now)
            else:
                self.db.execute(
                    "UPDATE fleet_contract_state SET status=?,owner_role='JUDGE',claimed_by=NULL,lease_until=NULL,updated_at=?,terminal_reason=? WHERE contract_id=?",
                    (verdict, created_at, details.get("reason", verdict), row["contract_id"]),
                )
            self._append_event("VERDICT_RECORDED", verdict_id,
                {"contract_id": row["contract_id"], "result_id": result_id, "verdict": verdict, "verdict_hash": verdict_hash}, now=now)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"verdict_id": verdict_id, "verdict_hash": verdict_hash, "verdict": verdict, "created": True}

    def record_error_event(self, *, subsystem: str, event_type: str, severity: str, recovered: bool,
                           details: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        now = now or _utc_now()
        body = {"subsystem": subsystem, "event_type": event_type, "severity": severity,
                "recovered": bool(recovered), "occurred_at": _iso(now), "details": details}
        digest = sha256_json(body)
        error_id = f"error:{digest[:32]}"
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "INSERT OR IGNORE INTO fleet_error_events (error_id,subsystem,event_type,severity,recovered,occurred_at,details_json,event_hash) VALUES (?,?,?,?,?,?,?,?)",
                (error_id,subsystem,event_type,severity,int(recovered),body["occurred_at"],canonical_json(details),digest),
            )
            self._append_event("ERROR_RECORDED", error_id,
                {"subsystem": subsystem, "event_type": event_type, "recovered": bool(recovered)}, now=now)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"error_id": error_id, "error_hash": digest, "budget": self.error_budget(subsystem, now=now)}

    def metrics(self, *, now: datetime | None = None, persist: bool = False) -> dict[str, Any]:
        now = now or _utc_now()
        state_rows = self.db.execute("SELECT status,attempt_count FROM fleet_contract_state").fetchall()
        verdict_rows = self.db.execute("SELECT verdict FROM fleet_verdicts").fetchall()
        total = len(state_rows)
        solved = sum(row["status"] in SUCCESS_STATES for row in state_rows)
        failed = sum(row["status"] == "FAILED_PRESERVED" for row in state_rows)
        blocked = sum(row["status"] in {"BLOCKED_EXTERNAL","BLOCKED_DEPENDENCY"} for row in state_rows)
        verification_failed = sum(row["verdict"] == "VERIFICATION_FAILED" for row in verdict_rows)
        verification_total = len(verdict_rows)
        metrics = {
            "captured_at": _iso(now), "contracts_total": total, "solved": solved, "failed": failed,
            "blocked": blocked, "open": total - solved - failed - blocked,
            "solve_fraction": solved / total if total else 1.0,
            "verification_total": verification_total, "verification_failed": verification_failed,
            "verification_failure_rate": verification_failed / verification_total if verification_total else 0.0,
            "mean_attempts": sum(int(row["attempt_count"]) for row in state_rows) / total if total else 0.0,
            "event_chain_valid": self.verify_event_chain(),
        }
        if persist:
            digest = sha256_json(metrics)
            snapshot_id = f"metric:{digest[:32]}"
            self.db.execute(
                "INSERT OR IGNORE INTO fleet_metric_snapshots (snapshot_id,captured_at,metrics_json,metrics_hash) VALUES (?,?,?,?)",
                (snapshot_id, metrics["captured_at"], canonical_json(metrics), digest),
            )
            self.db.commit()
            metrics["snapshot_id"] = snapshot_id
            metrics["metrics_hash"] = digest
        return metrics

    def status(self) -> dict[str, Any]:
        roles = {}
        for role in ROLES:
            rows = self.db.execute(
                "SELECT status,COUNT(*) count FROM fleet_contract_state WHERE owner_role=? GROUP BY status",
                (role,),
            ).fetchall()
            roles[role] = {row["status"]: row["count"] for row in rows}
        subsystems = [row["subsystem"] for row in self.db.execute("SELECT DISTINCT subsystem FROM fleet_error_events")]
        return {"roles": roles, "metrics": self.metrics(),
                "contracted_subsystems": [budget for subsystem in subsystems if (budget := self.error_budget(subsystem))["contracted"]],
                "pending_verification": len(self.pending_verification(limit=100)),
                "event_chain_valid": self.verify_event_chain()}
