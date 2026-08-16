from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def hourly_epoch(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValueError("epoch source must be timezone-aware")
    return int(value.astimezone(UTC).timestamp() // 3600)


class Phase(StrEnum):
    BUILD = "BUILD"
    EVOLVE = "EVOLVE"
    VERIFY = "VERIFY"
    RECOVER = "RECOVER"
    OPERATE = "OPERATE"


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ExecutionMode(StrEnum):
    DIRECT = "DIRECT"
    CANARY = "CANARY"


class SagaState(StrEnum):
    COMMITTED = "COMMITTED"
    COMPENSATED = "COMPENSATED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    kind: str
    subject: str
    source: str
    acquired_at: str
    ttl_seconds: int
    digest: str
    provenance: str
    run_id: str
    epoch: int

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.kind or not self.subject or not self.source:
            raise ValueError("evidence identity fields must be non-empty")
        if self.ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")
        if len(self.digest) != 64 or any(c not in "0123456789abcdef" for c in self.digest):
            raise ValueError("digest must be a lowercase SHA-256 hex string")
        if self.provenance not in {"internal", "external"}:
            raise ValueError("provenance must be internal or external")
        acquired = parse_time(self.acquired_at)
        if self.epoch != hourly_epoch(acquired):
            raise ValueError("evidence epoch must match acquired_at hourly epoch")

    def expires_at(self) -> datetime:
        return parse_time(self.acquired_at) + timedelta(seconds=self.ttl_seconds)

    def is_fresh(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return now.astimezone(UTC) <= self.expires_at()


@dataclass(frozen=True)
class MutationContract:
    operation_id: str
    authority: str
    actor_identity: str
    target_identity: str
    preconditions: tuple[str, ...]
    blast_radius: int
    rollback_plan: str
    postconditions: tuple[str, ...]
    idempotency_key: str
    evidence_required: tuple[str, ...]
    canary_supported: bool = False
    consequential: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.blast_radius <= 3:
            raise ValueError("blast_radius must be in [0, 3]")

    def digest(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True)
class ProofResult:
    passed: bool
    reasons: tuple[str, ...]
    contract_digest: str
    evidence_digests: tuple[str, ...]
    execution_mode: ExecutionMode | None


def prove_mutation(
    contract: MutationContract,
    evidence: Sequence[EvidenceRecord],
    observed_preconditions: Mapping[str, bool],
    *,
    now: datetime,
    ledger: OperationLedger | None = None,
    canary_threshold: int = 2,
) -> ProofResult:
    reasons: list[str] = []
    required_text = {
        "operation_id": contract.operation_id,
        "authority": contract.authority,
        "actor_identity": contract.actor_identity,
        "target_identity": contract.target_identity,
        "rollback_plan": contract.rollback_plan,
        "idempotency_key": contract.idempotency_key,
    }
    reasons.extend(f"missing:{name}" for name, value in required_text.items() if not value.strip())
    if not contract.preconditions:
        reasons.append("missing:preconditions")
    if not contract.postconditions:
        reasons.append("missing:postconditions")
    if not contract.evidence_required:
        reasons.append("missing:evidence_required")

    for name in contract.preconditions:
        if observed_preconditions.get(name) is not True:
            reasons.append(f"precondition_failed:{name}")

    by_kind: dict[str, list[EvidenceRecord]] = {}
    for record in evidence:
        by_kind.setdefault(record.kind, []).append(record)

    expected_subjects = {
        "authority": contract.authority,
        "identity": contract.actor_identity,
        "target": contract.target_identity,
        "preconditions": contract.target_identity,
    }
    evidence_digests: list[str] = []
    for kind in contract.evidence_required:
        candidates = by_kind.get(kind, [])
        if not candidates:
            reasons.append(f"evidence_missing:{kind}")
            continue
        fresh = [record for record in candidates if record.is_fresh(now)]
        if not fresh:
            reasons.append(f"evidence_stale:{kind}")
            continue
        expected_subject = expected_subjects.get(kind)
        if expected_subject is not None:
            bound = [record for record in fresh if record.subject == expected_subject]
            if not bound:
                reasons.append(f"evidence_subject_mismatch:{kind}")
                continue
            fresh = bound
        selected = max(fresh, key=lambda record: parse_time(record.acquired_at))
        evidence_digests.append(selected.digest)

    if ledger is not None and ledger.contains(contract.idempotency_key):
        reasons.append("idempotency_key_already_committed")

    mode = None
    if not reasons:
        mode = (
            ExecutionMode.CANARY
            if contract.blast_radius >= canary_threshold and contract.canary_supported
            else ExecutionMode.DIRECT
        )

    return ProofResult(
        passed=not reasons,
        reasons=tuple(sorted(set(reasons))),
        contract_digest=contract.digest(),
        evidence_digests=tuple(sorted(evidence_digests)),
        execution_mode=mode,
    )


@dataclass(frozen=True)
class DebtPolicy:
    max_verification_debt: int = 0
    max_deployment_debt: int = 0


@dataclass(frozen=True)
class DebtState:
    verification_debt: int = 0
    deployment_debt: int = 0

    def permits(self, phase: Phase, policy: DebtPolicy) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if phase in {Phase.BUILD, Phase.EVOLVE}:
            if self.verification_debt > policy.max_verification_debt:
                reasons.append("verification_debt")
            if self.deployment_debt > policy.max_deployment_debt:
                reasons.append("deployment_debt")
        return not reasons, tuple(reasons)


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_seconds: int = 3600
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    opened_at: str | None = None
    half_open_trial_used: bool = False

    def allow(self, now: datetime) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_trial_used:
                return False
            self.half_open_trial_used = True
            return True
        if self.opened_at is None:
            return False
        opened = parse_time(self.opened_at)
        if now.astimezone(UTC) < opened + timedelta(seconds=self.cooldown_seconds):
            return False
        self.state = CircuitState.HALF_OPEN
        self.half_open_trial_used = True
        return True

    def success(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = None
        self.half_open_trial_used = False

    def failure(self, now: datetime) -> None:
        self.failure_count += 1
        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = now.astimezone(UTC).isoformat()
            self.half_open_trial_used = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        return value


@dataclass(frozen=True)
class ComponentState:
    component: str
    verification_debt: int
    deployment_debt: int
    failure_streak: int
    circuit_state: CircuitState
    opened_at: str | None
    last_revalidated_at: str | None
    drift_status: str


@dataclass(frozen=True)
class RevalidationPolicy:
    intervals_seconds: tuple[int, int, int, int] = (604800, 259200, 86400, 21600)

    def due(self, last_revalidated_at: str | None, blast_radius: int, now: datetime) -> bool:
        if not 0 <= blast_radius <= 3:
            raise ValueError("blast_radius must be in [0, 3]")
        if last_revalidated_at is None:
            return True
        last = parse_time(last_revalidated_at)
        return now.astimezone(UTC) >= last + timedelta(
            seconds=self.intervals_seconds[blast_radius]
        )


@dataclass(frozen=True)
class Checkpoint:
    schema: str
    run_id: str
    epoch: int
    phase: Phase
    immutable_inputs_digest: str
    result_digests: tuple[str, ...]
    pending_obligations: tuple[str, ...]
    state_digest: str
    resume_digest: str

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        epoch: int,
        phase: Phase,
        immutable_inputs: Any,
        result_digests: Sequence[str],
        pending_obligations: Sequence[str],
        state: Any,
    ) -> Checkpoint:
        body = {
            "schema": "centinal26-checkpoint-v1",
            "run_id": run_id,
            "epoch": epoch,
            "phase": phase.value,
            "immutable_inputs_digest": canonical_sha256(immutable_inputs),
            "result_digests": sorted(result_digests),
            "pending_obligations": sorted(pending_obligations),
            "state_digest": canonical_sha256(state),
        }
        return cls(
            schema=body["schema"],
            run_id=run_id,
            epoch=epoch,
            phase=phase,
            immutable_inputs_digest=body["immutable_inputs_digest"],
            result_digests=tuple(body["result_digests"]),
            pending_obligations=tuple(body["pending_obligations"]),
            state_digest=body["state_digest"],
            resume_digest=canonical_sha256(body),
        )

    def verify(self) -> bool:
        body = {
            "schema": self.schema,
            "run_id": self.run_id,
            "epoch": self.epoch,
            "phase": self.phase.value,
            "immutable_inputs_digest": self.immutable_inputs_digest,
            "result_digests": list(self.result_digests),
            "pending_obligations": list(self.pending_obligations),
            "state_digest": self.state_digest,
        }
        return canonical_sha256(body) == self.resume_digest

    def assert_resume(self, immutable_inputs: Any, state: Any) -> None:
        if not self.verify():
            raise ValueError("checkpoint resume digest mismatch")
        if canonical_sha256(immutable_inputs) != self.immutable_inputs_digest:
            raise ValueError("immutable inputs changed since checkpoint")
        if canonical_sha256(state) != self.state_digest:
            raise ValueError("restored state differs from checkpoint")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["phase"] = self.phase.value
        return value


@dataclass(frozen=True)
class PromotionClaim:
    result_digest: str
    build_run_id: str
    build_epoch: int
    verification_run_id: str
    verification_epoch: int
    external_evidence_ids: tuple[str, ...]


def prove_promotion(
    claim: PromotionClaim,
    evidence: Sequence[EvidenceRecord],
    *,
    now: datetime,
) -> ProofResult:
    reasons: list[str] = []
    if claim.verification_epoch <= claim.build_epoch:
        reasons.append("verification_must_cross_hourly_epoch")
    if claim.verification_run_id == claim.build_run_id:
        reasons.append("verification_must_use_distinct_run")
    by_id = {record.evidence_id: record for record in evidence}
    selected: list[EvidenceRecord] = []
    if not claim.external_evidence_ids:
        reasons.append("external_evidence_required")
    for evidence_id in claim.external_evidence_ids:
        record = by_id.get(evidence_id)
        if record is None:
            reasons.append(f"external_evidence_missing:{evidence_id}")
            continue
        selected.append(record)
        if record.provenance != "external":
            reasons.append(f"external_evidence_not_external:{evidence_id}")
        if not record.is_fresh(now):
            reasons.append(f"external_evidence_stale:{evidence_id}")
        if record.epoch < claim.verification_epoch:
            reasons.append(f"external_evidence_predates_verification:{evidence_id}")

    return ProofResult(
        passed=not reasons,
        reasons=tuple(sorted(set(reasons))),
        contract_digest=claim.result_digest,
        evidence_digests=tuple(sorted(record.digest for record in selected)),
        execution_mode=None,
    )


@dataclass(frozen=True)
class SagaStep:
    name: str
    forward: Callable[[], Any]
    postcondition: Callable[[Any], bool]
    compensate: Callable[[Any], Any]
    compensation_postcondition: Callable[[Any], bool]


@dataclass(frozen=True)
class SagaResult:
    state: SagaState
    completed: tuple[str, ...]
    compensated: tuple[str, ...]
    error: str | None


class SagaRunner:
    def execute(self, steps: Sequence[SagaStep]) -> SagaResult:
        completed: list[tuple[SagaStep, Any]] = []
        try:
            for step in steps:
                result = step.forward()
                if not step.postcondition(result):
                    raise RuntimeError(f"postcondition_failed:{step.name}")
                completed.append((step, result))
        except Exception as error:  # noqa: BLE001 - transaction boundary converts to evidence
            compensated: list[str] = []
            compensation_errors: list[str] = []
            for step, forward_result in reversed(completed):
                try:
                    compensation = step.compensate(forward_result)
                    if not step.compensation_postcondition(compensation):
                        compensation_errors.append(
                            f"compensation_postcondition_failed:{step.name}"
                        )
                    else:
                        compensated.append(step.name)
                except Exception as compensation_error:  # noqa: BLE001 - evidence boundary
                    compensation_errors.append(
                        f"compensation_failed:{step.name}:{type(compensation_error).__name__}"
                    )
            state = (
                SagaState.COMPENSATION_FAILED
                if compensation_errors
                else SagaState.COMPENSATED
            )
            details = [f"{type(error).__name__}:{error}", *compensation_errors]
            return SagaResult(
                state=state,
                completed=tuple(step.name for step, _ in completed),
                compensated=tuple(compensated),
                error=";".join(details),
            )
        return SagaResult(
            state=SagaState.COMMITTED,
            completed=tuple(step.name for step, _ in completed),
            compensated=(),
            error=None,
        )


class OperationLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("operation ledger must contain a JSON object")
        return {str(key): str(item) for key, item in value.items()}

    def contains(self, idempotency_key: str) -> bool:
        return idempotency_key in self._read()

    def record(self, idempotency_key: str, result_digest: str) -> None:
        data = self._read()
        existing = data.get(idempotency_key)
        if existing is not None and existing != result_digest:
            raise ValueError("idempotency key already committed to a different result")
        data[idempotency_key] = result_digest
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.path)


class ReentrancyGuard:
    def __init__(self, path: Path, run_id: str, *, lease_seconds: int = 7200):
        self.path = path
        self.run_id = run_id
        self.lease_seconds = lease_seconds
        self.acquired = False

    def _payload(self, now: datetime) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pid": os.getpid(),
            "acquired_at": now.astimezone(UTC).isoformat(),
            "lease_seconds": self.lease_seconds,
        }

    def _try_create(self, now: datetime) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        try:
            payload = json.dumps(self._payload(now), sort_keys=True).encode("utf-8")
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        self.acquired = True
        return True

    def acquire(self, now: datetime | None = None) -> None:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        if self._try_create(current):
            return
        try:
            active = json.loads(self.path.read_text(encoding="utf-8"))
            acquired_at = parse_time(str(active["acquired_at"]))
            lease_seconds = int(active.get("lease_seconds", self.lease_seconds))
            stale = current > acquired_at + timedelta(seconds=lease_seconds)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            stale = False
        if not stale:
            raise RuntimeError("controller_reentrancy_blocked")
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        if not self._try_create(current):
            raise RuntimeError("controller_reentrancy_race_lost")

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            active = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            active = {}
        if active.get("run_id") == self.run_id:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self.acquired = False

    def __enter__(self) -> ReentrancyGuard:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
