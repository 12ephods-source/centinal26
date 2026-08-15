from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_sha256(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class EffectState(StrEnum):
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"
    AUTHORIZED = "AUTHORIZED"
    CLAIMED = "CLAIMED"
    EXECUTING = "EXECUTING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    PUBLISHED = "PUBLISHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DENIED = "DENIED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = {
    EffectState.ACKNOWLEDGED,
    EffectState.DENIED,
    EffectState.FAILED_TERMINAL,
    EffectState.VERIFICATION_FAILED,
    EffectState.CANCELLED,
}


@dataclass(frozen=True)
class EffectRequest:
    capability: str
    payload: Json
    idempotency_key: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    actor: str = "local-user"
    expires_at: str | None = None
    created_at: str = field(default_factory=_now)

    @property
    def sha256(self) -> str:
        return _canonical_sha256(asdict(self))


@dataclass(frozen=True)
class EffectAuthorization:
    authorization_id: str
    request_sha256: str
    capability: str
    actor: str
    approved: bool
    expires_at: str
    constraints: Json = field(default_factory=dict)

    def valid_for(self, request: EffectRequest) -> bool:
        try:
            expires = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return False
        return (
            self.approved
            and self.request_sha256 == request.sha256
            and self.capability == request.capability
            and expires > datetime.now(UTC)
        )


@dataclass(frozen=True)
class EffectClaim:
    effect_id: str
    claim_token: str
    worker_id: str
    lease_until: str
    attempt: int


@dataclass(frozen=True)
class EffectSnapshot:
    effect_id: str
    state: EffectState
    request: EffectRequest
    attempts: int
    max_attempts: int
    authorization: Json | None
    execution_intent: Json | None
    execution_result: Json | None
    verification: Json | None
    publication: Json | None
    acknowledgement: Json | None
    claim_worker: str | None
    claim_until: str | None
    created_at: str
    updated_at: str


class EffectConflict(ValueError):
    """An idempotency key was reused for a different immutable request."""


class EffectTransitionError(RuntimeError):
    """The requested state transition is not permitted."""


class EffectProtocolLedger:
    """Durable frost-effect/1.0 control ledger.

    The ledger deliberately does not perform arbitrary side effects. It persists the
    authorization, claim, execution intent, provider idempotency identity, execution
    result, independent verification, publication, and acknowledgement boundaries.

    A crash after EXECUTING is treated as RECOVERY_REQUIRED. It is never silently
    retried because the external effect may already have occurred.
    """

    schema = "frost-effect/1.0"

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS effects (
                effect_id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                request_sha256 TEXT NOT NULL,
                request_json TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL,
                authorization_json TEXT,
                claim_token TEXT,
                claim_worker TEXT,
                claim_until TEXT,
                execution_intent_json TEXT,
                execution_result_json TEXT,
                verification_json TEXT,
                publication_json TEXT,
                acknowledgement_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS effect_history (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                effect_id TEXT NOT NULL,
                event TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_effect_state
                ON effects(state, created_at, effect_id);
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def submit(self, request: EffectRequest, max_attempts: int = 3) -> tuple[str, bool]:
        if not request.capability.strip():
            raise ValueError("capability must not be empty")
        if not request.idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._validate_request_expiry(request)
        effect_id = str(uuid.uuid4())
        stamp = _now()
        with self._lock:
            try:
                self.db.execute(
                    """
                    INSERT INTO effects(
                        effect_id,idempotency_key,request_sha256,request_json,state,
                        attempts,max_attempts,created_at,updated_at
                    ) VALUES(?,?,?,?,?,0,?,?,?)
                    """,
                    (
                        effect_id,
                        request.idempotency_key,
                        request.sha256,
                        json.dumps(asdict(request), sort_keys=True),
                        EffectState.PENDING_AUTHORIZATION.value,
                        max_attempts,
                        stamp,
                        stamp,
                    ),
                )
                self._append_history_locked(
                    effect_id,
                    "effect_submitted",
                    None,
                    EffectState.PENDING_AUTHORIZATION,
                    {"request_sha256": request.sha256},
                )
                self.db.commit()
                return effect_id, True
            except sqlite3.IntegrityError:
                self.db.rollback()
                row = self.db.execute(
                    "SELECT effect_id,request_sha256 FROM effects WHERE idempotency_key=?",
                    (request.idempotency_key,),
                ).fetchone()
                if row is None:
                    raise
                if row["request_sha256"] != request.sha256:
                    raise EffectConflict(
                        "idempotency key reused for a different immutable request"
                    )
                return str(row["effect_id"]), False

    def authorize(self, effect_id: str, authorization: EffectAuthorization) -> EffectState:
        with self._lock:
            row = self._row_locked(effect_id)
            state = EffectState(row["state"])
            if state in {EffectState.AUTHORIZED, EffectState.DENIED}:
                stored = self._loads(row["authorization_json"])
                if stored == asdict(authorization):
                    return state
                raise EffectTransitionError("authorization is already immutable")
            if state != EffectState.PENDING_AUTHORIZATION:
                raise EffectTransitionError(f"cannot authorize from {state}")
            request = self._request_from_row(row)
            approved = authorization.valid_for(request)
            next_state = EffectState.AUTHORIZED if approved else EffectState.DENIED
            self.db.execute(
                "UPDATE effects SET state=?,authorization_json=?,updated_at=? WHERE effect_id=?",
                (
                    next_state.value,
                    json.dumps(asdict(authorization), sort_keys=True),
                    _now(),
                    effect_id,
                ),
            )
            self._append_history_locked(
                effect_id,
                "authorization_approved" if approved else "authorization_denied",
                state,
                next_state,
                {"authorization_id": authorization.authorization_id},
            )
            self.db.commit()
            return next_state

    def claim(self, worker_id: str, lease_seconds: int = 60) -> EffectClaim | None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self.recover_expired_claims()
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                """
                SELECT * FROM effects
                WHERE state IN (?, ?)
                ORDER BY created_at,effect_id LIMIT 1
                """,
                (EffectState.AUTHORIZED.value, EffectState.FAILED_RETRYABLE.value),
            ).fetchone()
            if row is None:
                self.db.commit()
                return None
            request = self._request_from_row(row)
            if self._request_expired(request):
                self._transition_locked(
                    row,
                    EffectState.CANCELLED,
                    "request_expired_before_claim",
                    {"expires_at": request.expires_at},
                )
                self.db.commit()
                return None
            attempt = int(row["attempts"]) + 1
            if attempt > int(row["max_attempts"]):
                self._transition_locked(
                    row,
                    EffectState.FAILED_TERMINAL,
                    "attempt_budget_exhausted",
                    {},
                )
                self.db.commit()
                return None
            token = str(uuid.uuid4())
            lease_until = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
            self.db.execute(
                """
                UPDATE effects
                SET state=?,attempts=?,claim_token=?,claim_worker=?,claim_until=?,updated_at=?
                WHERE effect_id=?
                """,
                (
                    EffectState.CLAIMED.value,
                    attempt,
                    token,
                    worker_id,
                    lease_until,
                    _now(),
                    row["effect_id"],
                ),
            )
            self._append_history_locked(
                str(row["effect_id"]),
                "effect_claimed",
                EffectState(row["state"]),
                EffectState.CLAIMED,
                {"worker_id": worker_id, "attempt": attempt, "lease_until": lease_until},
            )
            self.db.commit()
            return EffectClaim(str(row["effect_id"]), token, worker_id, lease_until, attempt)

    def begin_execution(
        self,
        claim: EffectClaim,
        *,
        provider_id: str,
        provider_idempotency_key: str,
        operation: str,
    ) -> str:
        """Persist execution intent before invoking the provider.

        The returned execution_token must be bound to the provider call. For external
        side effects, the provider must support this idempotency identity or a later
        reconciliation/status lookup. Otherwise a crash cannot be made exactly-once.
        """
        if not provider_id.strip() or not provider_idempotency_key.strip() or not operation.strip():
            raise ValueError("provider_id, provider_idempotency_key, and operation are required")
        with self._lock:
            self._claimed_row_locked(claim)
            execution_token = str(uuid.uuid4())
            intent = {
                "schema": self.schema,
                "execution_token": execution_token,
                "provider_id": provider_id,
                "provider_idempotency_key": provider_idempotency_key,
                "operation": operation,
                "prepared_at": _now(),
            }
            self.db.execute(
                """
                UPDATE effects
                SET state=?,execution_intent_json=?,updated_at=?
                WHERE effect_id=?
                """,
                (
                    EffectState.EXECUTING.value,
                    json.dumps(intent, sort_keys=True),
                    _now(),
                    claim.effect_id,
                ),
            )
            self._append_history_locked(
                claim.effect_id,
                "execution_intent_persisted",
                EffectState.CLAIMED,
                EffectState.EXECUTING,
                intent,
            )
            self.db.commit()
            return execution_token

    def record_execution(
        self,
        effect_id: str,
        execution_token: str,
        result: Json,
        provider_receipt: Json,
    ) -> EffectState:
        with self._lock:
            row = self._row_locked(effect_id)
            state = EffectState(row["state"])
            if state == EffectState.EXECUTED:
                stored = self._loads(row["execution_result_json"])
                if stored and stored.get("execution_token") == execution_token:
                    return state
                raise EffectTransitionError("execution result is already immutable")
            if state not in {EffectState.EXECUTING, EffectState.RECOVERY_REQUIRED}:
                raise EffectTransitionError(f"cannot record execution from {state}")
            intent = self._loads(row["execution_intent_json"])
            if not intent or intent.get("execution_token") != execution_token:
                raise EffectTransitionError("execution token does not match persisted intent")
            record = {
                "execution_token": execution_token,
                "result": result,
                "provider_receipt": provider_receipt,
                "result_sha256": _canonical_sha256(result),
                "recorded_at": _now(),
            }
            self.db.execute(
                "UPDATE effects SET state=?,execution_result_json=?,updated_at=? WHERE effect_id=?",
                (
                    EffectState.EXECUTED.value,
                    json.dumps(record, sort_keys=True),
                    _now(),
                    effect_id,
                ),
            )
            self._append_history_locked(
                effect_id,
                "execution_recorded",
                state,
                EffectState.EXECUTED,
                {"result_sha256": record["result_sha256"]},
            )
            self.db.commit()
            return EffectState.EXECUTED

    def mark_execution_failure(
        self,
        claim: EffectClaim,
        error: Json,
        *,
        provider_not_invoked: bool,
    ) -> EffectState:
        """Record failure safely.

        A retryable state is allowed only when the provider is known not to have been
        invoked. Otherwise the effect moves to RECOVERY_REQUIRED for reconciliation.
        """
        with self._lock:
            row = self._row_locked(claim.effect_id)
            self._validate_claim_identity(row, claim)
            state = EffectState(row["state"])
            if state not in {EffectState.CLAIMED, EffectState.EXECUTING}:
                raise EffectTransitionError(f"cannot record execution failure from {state}")
            if provider_not_invoked:
                next_state = (
                    EffectState.FAILED_RETRYABLE
                    if int(row["attempts"]) < int(row["max_attempts"])
                    else EffectState.FAILED_TERMINAL
                )
            else:
                next_state = EffectState.RECOVERY_REQUIRED
            self._transition_locked(
                row,
                next_state,
                "execution_failure_recorded",
                {"error": error, "provider_not_invoked": provider_not_invoked},
                clear_claim=provider_not_invoked,
            )
            self.db.commit()
            return next_state

    def verify(
        self,
        effect_id: str,
        *,
        verifier_id: str,
        passed: bool,
        evidence: Json,
        independent: bool,
    ) -> EffectState:
        if not verifier_id.strip():
            raise ValueError("verifier_id must not be empty")
        with self._lock:
            row = self._row_locked(effect_id)
            state = EffectState(row["state"])
            if state in {EffectState.VERIFIED, EffectState.VERIFICATION_FAILED}:
                stored = self._loads(row["verification_json"])
                if stored and stored.get("verifier_id") == verifier_id and bool(
                    stored.get("passed")
                ) == passed:
                    return state
                raise EffectTransitionError("verification is already immutable")
            if state != EffectState.EXECUTED:
                raise EffectTransitionError(f"cannot verify from {state}")
            execution = self._loads(row["execution_result_json"])
            assert execution is not None
            verification = {
                "verifier_id": verifier_id,
                "passed": passed,
                "independent": independent,
                "execution_result_sha256": _canonical_sha256(execution),
                "evidence": evidence,
                "verified_at": _now(),
            }
            accepted = passed and independent
            next_state = EffectState.VERIFIED if accepted else EffectState.VERIFICATION_FAILED
            self.db.execute(
                "UPDATE effects SET state=?,verification_json=?,updated_at=? WHERE effect_id=?",
                (
                    next_state.value,
                    json.dumps(verification, sort_keys=True),
                    _now(),
                    effect_id,
                ),
            )
            self._append_history_locked(
                effect_id,
                "verification_passed" if accepted else "verification_failed",
                state,
                next_state,
                {
                    "verifier_id": verifier_id,
                    "passed": passed,
                    "independent": independent,
                },
            )
            self.db.commit()
            return next_state

    def publish(self, effect_id: str, publication: Json) -> EffectState:
        with self._lock:
            row = self._row_locked(effect_id)
            state = EffectState(row["state"])
            if state == EffectState.PUBLISHED:
                if self._loads(row["publication_json"]) == publication:
                    return state
                raise EffectTransitionError("publication is already immutable")
            if state != EffectState.VERIFIED:
                raise EffectTransitionError(f"cannot publish from {state}")
            self.db.execute(
                "UPDATE effects SET state=?,publication_json=?,updated_at=? WHERE effect_id=?",
                (
                    EffectState.PUBLISHED.value,
                    json.dumps(publication, sort_keys=True),
                    _now(),
                    effect_id,
                ),
            )
            self._append_history_locked(
                effect_id,
                "result_published",
                state,
                EffectState.PUBLISHED,
                {"publication_sha256": _canonical_sha256(publication)},
            )
            self.db.commit()
            return EffectState.PUBLISHED

    def acknowledge(self, effect_id: str, acknowledgement: Json) -> EffectState:
        with self._lock:
            row = self._row_locked(effect_id)
            state = EffectState(row["state"])
            if state == EffectState.ACKNOWLEDGED:
                if self._loads(row["acknowledgement_json"]) == acknowledgement:
                    return state
                raise EffectTransitionError("acknowledgement is already immutable")
            if state != EffectState.PUBLISHED:
                raise EffectTransitionError(f"cannot acknowledge from {state}")
            self.db.execute(
                "UPDATE effects SET state=?,acknowledgement_json=?,updated_at=? WHERE effect_id=?",
                (
                    EffectState.ACKNOWLEDGED.value,
                    json.dumps(acknowledgement, sort_keys=True),
                    _now(),
                    effect_id,
                ),
            )
            self._append_history_locked(
                effect_id,
                "delivery_acknowledged",
                state,
                EffectState.ACKNOWLEDGED,
                {"ack_sha256": _canonical_sha256(acknowledgement)},
            )
            self.db.commit()
            return EffectState.ACKNOWLEDGED

    def reconcile_execution(
        self,
        effect_id: str,
        *,
        execution_token: str,
        provider_status: str,
        result: Json | None = None,
        provider_receipt: Json | None = None,
    ) -> EffectState:
        """Resolve an uncertain EXECUTING effect after a crash/provider outage.

        `provider_status` must be one of `NOT_EXECUTED`, `EXECUTED`, or `UNKNOWN`.
        UNKNOWN remains fail-closed in RECOVERY_REQUIRED.
        """
        if provider_status not in {"NOT_EXECUTED", "EXECUTED", "UNKNOWN"}:
            raise ValueError("invalid provider_status")
        with self._lock:
            row = self._row_locked(effect_id)
            state = EffectState(row["state"])
            if state not in {EffectState.EXECUTING, EffectState.RECOVERY_REQUIRED}:
                raise EffectTransitionError(f"cannot reconcile execution from {state}")
            intent = self._loads(row["execution_intent_json"])
            if not intent or intent.get("execution_token") != execution_token:
                raise EffectTransitionError("execution token does not match persisted intent")
            if provider_status == "UNKNOWN":
                self._transition_locked(
                    row,
                    EffectState.RECOVERY_REQUIRED,
                    "provider_execution_unknown",
                    {"execution_token": execution_token},
                )
                self.db.commit()
                return EffectState.RECOVERY_REQUIRED
            if provider_status == "EXECUTED":
                if result is None or provider_receipt is None:
                    raise ValueError("executed reconciliation requires result and provider_receipt")
                self.db.rollback()
                return self.record_execution(effect_id, execution_token, result, provider_receipt)
            next_state = (
                EffectState.FAILED_RETRYABLE
                if int(row["attempts"]) < int(row["max_attempts"])
                else EffectState.FAILED_TERMINAL
            )
            self._transition_locked(
                row,
                next_state,
                "provider_confirmed_not_executed",
                {"execution_token": execution_token},
                clear_claim=True,
                clear_execution_intent=True,
            )
            self.db.commit()
            return next_state

    def recover_expired_claims(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        recovered = 0
        with self._lock:
            rows = self.db.execute(
                "SELECT * FROM effects WHERE state IN (?, ?) AND claim_until IS NOT NULL",
                (EffectState.CLAIMED.value, EffectState.EXECUTING.value),
            ).fetchall()
            for row in rows:
                try:
                    lease = datetime.fromisoformat(row["claim_until"])
                except ValueError:
                    lease = datetime.min.replace(tzinfo=UTC)
                if lease >= now:
                    continue
                state = EffectState(row["state"])
                if state == EffectState.CLAIMED:
                    next_state = (
                        EffectState.FAILED_RETRYABLE
                        if int(row["attempts"]) < int(row["max_attempts"])
                        else EffectState.FAILED_TERMINAL
                    )
                    clear = True
                    event = "claim_expired_before_execution"
                else:
                    next_state = EffectState.RECOVERY_REQUIRED
                    clear = False
                    event = "claim_expired_during_execution"
                self._transition_locked(
                    row,
                    next_state,
                    event,
                    {"lease_until": row["claim_until"]},
                    clear_claim=clear,
                )
                recovered += 1
            self.db.commit()
        return recovered

    def snapshot(self, effect_id: str) -> EffectSnapshot:
        with self._lock:
            row = self._row_locked(effect_id)
            return EffectSnapshot(
                effect_id=str(row["effect_id"]),
                state=EffectState(row["state"]),
                request=self._request_from_row(row),
                attempts=int(row["attempts"]),
                max_attempts=int(row["max_attempts"]),
                authorization=self._loads(row["authorization_json"]),
                execution_intent=self._loads(row["execution_intent_json"]),
                execution_result=self._loads(row["execution_result_json"]),
                verification=self._loads(row["verification_json"]),
                publication=self._loads(row["publication_json"]),
                acknowledgement=self._loads(row["acknowledgement_json"]),
                claim_worker=row["claim_worker"],
                claim_until=row["claim_until"],
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )

    def counts(self) -> dict[str, int]:
        with self._lock:
            rows = self.db.execute(
                "SELECT state,COUNT(*) AS n FROM effects GROUP BY state"
            ).fetchall()
            return {str(row["state"]): int(row["n"]) for row in rows}

    def history(self, effect_id: str) -> list[Json]:
        with self._lock:
            rows = self.db.execute(
                "SELECT * FROM effect_history WHERE effect_id=? ORDER BY sequence",
                (effect_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def verify_audit_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for row in self.db.execute("SELECT * FROM effect_history ORDER BY sequence"):
                record = {
                    "effect_id": row["effect_id"],
                    "event": row["event"],
                    "from_state": row["from_state"],
                    "to_state": row["to_state"],
                    "payload_json": row["payload_json"],
                    "timestamp": row["timestamp"],
                    "previous_hash": row["previous_hash"],
                }
                if record["previous_hash"] != previous:
                    return False
                found = _canonical_sha256(record)
                if found != row["hash"]:
                    return False
                previous = found
            return True

    def _append_history_locked(
        self,
        effect_id: str,
        event: str,
        from_state: EffectState | None,
        to_state: EffectState,
        payload: Json,
    ) -> None:
        row = self.db.execute(
            "SELECT hash FROM effect_history ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous = "0" * 64 if row is None else str(row["hash"])
        record = {
            "effect_id": effect_id,
            "event": event,
            "from_state": None if from_state is None else from_state.value,
            "to_state": to_state.value,
            "payload_json": json.dumps(payload, sort_keys=True),
            "timestamp": _now(),
            "previous_hash": previous,
        }
        digest = _canonical_sha256(record)
        self.db.execute(
            """
            INSERT INTO effect_history(
                effect_id,event,from_state,to_state,payload_json,timestamp,previous_hash,hash
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                effect_id,
                event,
                record["from_state"],
                record["to_state"],
                record["payload_json"],
                record["timestamp"],
                previous,
                digest,
            ),
        )

    def _row_locked(self, effect_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM effects WHERE effect_id=?", (effect_id,)).fetchone()
        if row is None:
            raise KeyError(effect_id)
        return row

    def _claimed_row_locked(self, claim: EffectClaim) -> sqlite3.Row:
        row = self._row_locked(claim.effect_id)
        if EffectState(row["state"]) != EffectState.CLAIMED:
            raise EffectTransitionError("effect is not currently claimed")
        self._validate_claim_identity(row, claim)
        if datetime.fromisoformat(str(row["claim_until"])) <= datetime.now(UTC):
            raise EffectTransitionError("claim lease has expired")
        return row

    @staticmethod
    def _validate_claim_identity(row: sqlite3.Row, claim: EffectClaim) -> None:
        if row["claim_token"] != claim.claim_token or row["claim_worker"] != claim.worker_id:
            raise EffectTransitionError("claim identity mismatch")

    def _transition_locked(
        self,
        row: sqlite3.Row,
        next_state: EffectState,
        event: str,
        payload: Json,
        *,
        clear_claim: bool = False,
        clear_execution_intent: bool = False,
    ) -> None:
        fields = ["state=?", "updated_at=?"]
        values: list[Any] = [next_state.value, _now()]
        if clear_claim:
            fields.extend(["claim_token=NULL", "claim_worker=NULL", "claim_until=NULL"])
        if clear_execution_intent:
            fields.append("execution_intent_json=NULL")
        values.append(row["effect_id"])
        self.db.execute(
            f"UPDATE effects SET {','.join(fields)} WHERE effect_id=?",
            values,
        )
        self._append_history_locked(
            str(row["effect_id"]),
            event,
            EffectState(row["state"]),
            next_state,
            payload,
        )

    @staticmethod
    def _loads(value: str | None) -> Json | None:
        return None if value is None else json.loads(value)

    @staticmethod
    def _request_from_row(row: sqlite3.Row) -> EffectRequest:
        return EffectRequest(**json.loads(row["request_json"]))

    @staticmethod
    def _validate_request_expiry(request: EffectRequest) -> None:
        if request.expires_at is None:
            return
        parsed = datetime.fromisoformat(request.expires_at)
        if parsed.tzinfo is None:
            raise ValueError("expires_at must include a timezone")

    @staticmethod
    def _request_expired(request: EffectRequest) -> bool:
        if request.expires_at is None:
            return False
        return datetime.fromisoformat(request.expires_at) <= datetime.now(UTC)
