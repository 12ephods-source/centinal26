from __future__ import annotations

import hashlib
import json
import signal
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .core import AuditLog, Grant, now_iso

Json = dict[str, Any]
Executor = Callable[[Json], Json]
Verifier = Callable[[Json, Json], bool]
Reducer = Callable[[Json, Json], Json]


@dataclass(frozen=True)
class Intent:
    capability: str
    payload: Json
    actor: str = "local-user"
    constraints: Json = field(default_factory=dict)
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=now_iso)


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    executor: Executor
    verifier: Verifier
    reducer: Reducer | None = None
    timeout_seconds: float = 30.0
    max_attempts: int = 3
    verifier_independent: bool = False


class RuntimeStore:
    """Durable queue, canonical state, leases, retries, and evolution evidence."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                intent TEXT NOT NULL, grant TEXT NOT NULL, capability TEXT NOT NULL,
                state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL, lease_until TEXT, result TEXT,
                evidence_path TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS canonical_state (
                key TEXT PRIMARY KEY, value TEXT NOT NULL, version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS run_history (
                run_id TEXT PRIMARY KEY, verified INTEGER NOT NULL,
                evidence_complete INTEGER NOT NULL, state_diverged INTEGER NOT NULL,
                recovery_test INTEGER NOT NULL DEFAULT 0,
                verifier_independent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def submit(
        self,
        intent: Intent,
        grant: Grant,
        key: str,
        max_attempts: int,
    ) -> tuple[str, bool]:
        job_id = str(uuid.uuid4())
        stamp = now_iso()
        try:
            self.db.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,?,'queued',0,?,NULL,NULL,NULL,?,?)",
                (
                    job_id,
                    key,
                    json.dumps(asdict(intent), sort_keys=True),
                    json.dumps(asdict(grant), sort_keys=True),
                    intent.capability,
                    max_attempts,
                    stamp,
                    stamp,
                ),
            )
            self.db.commit()
            return job_id, True
        except sqlite3.IntegrityError:
            self.db.rollback()
            row = self.db.execute(
                "SELECT id FROM jobs WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            if row is None:
                raise
            return str(row["id"]), False

    def recover(self) -> int:
        stamp = now_iso()
        rows = self.db.execute(
            "SELECT id,attempts,max_attempts FROM jobs "
            "WHERE state='running' AND lease_until IS NOT NULL AND lease_until<?",
            (stamp,),
        ).fetchall()
        for row in rows:
            state = "queued" if row["attempts"] < row["max_attempts"] else "failed"
            self.db.execute(
                "UPDATE jobs SET state=?,lease_until=NULL,updated_at=? WHERE id=?",
                (state, stamp, row["id"]),
            )
        self.db.commit()
        return len(rows)

    def claim(self, lease_seconds: int = 60) -> sqlite3.Row | None:
        self.recover()
        self.db.execute("BEGIN IMMEDIATE")
        row = self.db.execute(
            "SELECT * FROM jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1"
        ).fetchone()
        if row is None:
            self.db.commit()
            return None
        lease_until = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
        self.db.execute(
            "UPDATE jobs SET state='running',attempts=attempts+1,lease_until=?,updated_at=? "
            "WHERE id=? AND state='queued'",
            (lease_until, now_iso(), row["id"]),
        )
        self.db.commit()
        return self.db.execute(
            "SELECT * FROM jobs WHERE id=?",
            (row["id"],),
        ).fetchone()

    def finish(
        self,
        job_id: str,
        state: str,
        result: Json,
        evidence: str | None,
    ) -> None:
        self.db.execute(
            "UPDATE jobs SET state=?,result=?,evidence_path=?,lease_until=NULL,updated_at=? "
            "WHERE id=?",
            (state, json.dumps(result, sort_keys=True), evidence, now_iso(), job_id),
        )
        self.db.commit()

    def retry(self, job_id: str, result: Json, evidence: str) -> str:
        row = self.db.execute(
            "SELECT attempts,max_attempts FROM jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        state = "queued" if row["attempts"] < row["max_attempts"] else "failed"
        self.finish(job_id, state, result, evidence)
        return state

    def get_state(self, key: str) -> Json | None:
        row = self.db.execute(
            "SELECT value FROM canonical_state WHERE key=?",
            (key,),
        ).fetchone()
        return None if row is None else json.loads(row["value"])

    def set_state(self, key: str, value: Json) -> int:
        row = self.db.execute(
            "SELECT version FROM canonical_state WHERE key=?",
            (key,),
        ).fetchone()
        version = 1 if row is None else int(row["version"]) + 1
        self.db.execute(
            "INSERT INTO canonical_state VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value,version=excluded.version,updated_at=excluded.updated_at",
            (key, json.dumps(value, sort_keys=True), version, now_iso()),
        )
        self.db.commit()
        return version

    def record(
        self,
        verified: bool,
        evidence: bool,
        recovery: bool,
        independent: bool,
    ) -> None:
        self.db.execute(
            "INSERT INTO run_history VALUES(?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                int(verified),
                int(evidence),
                0,
                int(recovery),
                int(independent),
                now_iso(),
            ),
        )
        self.db.commit()

    def counts(self) -> Json:
        rows = self.db.execute(
            "SELECT state,COUNT(*) n FROM jobs GROUP BY state"
        ).fetchall()
        return {row["state"]: row["n"] for row in rows}

    def evolution_status(self, minimum: int = 10) -> Json:
        rows = self.db.execute(
            "SELECT * FROM run_history ORDER BY created_at DESC"
        ).fetchall()
        consecutive = 0
        for row in rows:
            if row["verified"] and row["evidence_complete"] and not row["state_diverged"]:
                consecutive += 1
            else:
                break
        zero_divergence = not any(row["state_diverged"] for row in rows)
        evidence_complete = bool(rows) and all(row["evidence_complete"] for row in rows)
        recovery_pass = any(
            row["recovery_test"] and row["verified"] for row in rows
        )
        verifier_independent = bool(rows) and all(
            row["verifier_independent"] for row in rows
        )
        ready = (
            consecutive >= minimum
            and zero_divergence
            and evidence_complete
            and recovery_pass
            and verifier_independent
        )
        return {
            "ready": ready,
            "consecutive_passes": consecutive,
            "minimum_consecutive_passes": minimum,
            "zero_state_divergence": zero_divergence,
            "evidence_complete": evidence_complete,
            "recovery_pass": recovery_pass,
            "verifier_independent": verifier_independent,
        }


class EvidenceStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def write(self, job_id: str, attempt: int, kind: str, payload: Json) -> Path:
        body = {
            **payload,
            "job_id": job_id,
            "attempt": attempt,
            "recorded_at": now_iso(),
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body["sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
        folder = self.root / job_id
        folder.mkdir(exist_ok=True)
        path = folder / f"{attempt:04d}-{kind}.json"
        if path.exists():
            raise FileExistsError(path)
        temp = path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(body, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
        return path

    @staticmethod
    def verify(path: Path) -> bool:
        body = json.loads(path.read_text(encoding="utf-8"))
        found = body.pop("sha256", None)
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return found == hashlib.sha256(canonical.encode()).hexdigest()


class AutomatedEngine:
    """Intent-to-state engine with evidence-gated state commits and recovery."""

    def __init__(
        self,
        store: RuntimeStore,
        audit: AuditLog,
        evidence: EvidenceStore,
    ):
        self.store = store
        self.audit = audit
        self.evidence = evidence
        self.capabilities: dict[str, CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec) -> None:
        if spec.timeout_seconds <= 0 or spec.max_attempts < 1:
            raise ValueError("capability bounds must be positive")
        self.capabilities[spec.name] = spec
        self.audit.append("capability_registered", {"capability": spec.name})

    def submit(
        self,
        intent: Intent,
        grant: Grant,
        idempotency_key: str | None = None,
    ) -> str:
        if not grant.permits(intent.capability):
            self.audit.append(
                "authorization_denied",
                {
                    "intent_id": intent.intent_id,
                    "capability": intent.capability,
                },
            )
            raise PermissionError("grant does not authorize requested capability")
        spec = self.capabilities.get(intent.capability)
        if spec is None:
            self.audit.append(
                "capability_unavailable",
                {
                    "intent_id": intent.intent_id,
                    "capability": intent.capability,
                },
            )
            raise KeyError(f"unknown capability: {intent.capability}")
        key = idempotency_key or f"intent:{intent.intent_id}"
        job_id, created = self.store.submit(intent, grant, key, spec.max_attempts)
        self.audit.append(
            "job_queued" if created else "job_deduplicated",
            {
                "job_id": job_id,
                "intent_id": intent.intent_id,
                "capability": intent.capability,
            },
        )
        return job_id

    def _execute(self, spec: CapabilitySpec, payload: Json) -> tuple[Json, float]:
        started = time.monotonic()
        alarm = (
            hasattr(signal, "setitimer")
            and hasattr(signal, "SIGALRM")
            and threading.current_thread() is threading.main_thread()
        )

        def timeout_handler(_signum, _frame):
            raise TimeoutError(
                f"capability exceeded {spec.timeout_seconds:.3f}s bound"
            )

        previous_handler = None
        if alarm:
            previous_handler = signal.getsignal(signal.SIGALRM)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, spec.timeout_seconds)
        try:
            output = spec.executor(payload)
        finally:
            if alarm:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous_handler)
        elapsed = time.monotonic() - started
        if elapsed > spec.timeout_seconds:
            raise TimeoutError(
                f"capability exceeded {spec.timeout_seconds:.3f}s bound ({elapsed:.3f}s)"
            )
        return output, elapsed

    def _record_failure(
        self,
        *,
        job_id: str,
        attempt: int,
        intent: Intent,
        spec: CapabilitySpec,
        result: Json,
        recovery_test: bool,
    ) -> str:
        evidence_path = self.evidence.write(
            job_id,
            attempt,
            "execution-failure",
            {
                "intent": asdict(intent),
                "capability": spec.name,
                "execution_error": result,
            },
        )
        state = self.store.retry(job_id, result, str(evidence_path))
        self.audit.append(f"job_{state}", {"job_id": job_id, **result})
        self.store.record(
            False,
            self.evidence.verify(evidence_path),
            recovery_test,
            spec.verifier_independent,
        )
        return job_id

    def run_once(self, recovery_test: bool = False) -> str | None:
        row = self.store.claim()
        if row is None:
            return None
        job_id = str(row["id"])
        attempt = int(row["attempts"])
        intent = Intent(**json.loads(row["intent"]))
        grant = Grant(**json.loads(row["grant"]))
        spec = self.capabilities.get(row["capability"])
        self.audit.append(
            "job_started",
            {
                "job_id": job_id,
                "attempt": attempt,
                "capability": row["capability"],
            },
        )

        if spec is None or not grant.permits(row["capability"]):
            result = {
                "ok": False,
                "error": "authorization_or_capability_invalid",
            }
            evidence_path = self.evidence.write(
                job_id,
                attempt,
                "rejected",
                {"intent": asdict(intent), "result": result},
            )
            self.store.finish(job_id, "rejected", result, str(evidence_path))
            self.audit.append("job_rejected", {"job_id": job_id, **result})
            self.store.record(
                False,
                self.evidence.verify(evidence_path),
                recovery_test,
                False,
            )
            return job_id

        try:
            output, elapsed = self._execute(spec, intent.payload)
        except Exception as error:  # noqa: BLE001 - capability boundary captures failures
            return self._record_failure(
                job_id=job_id,
                attempt=attempt,
                intent=intent,
                spec=spec,
                result={
                    "ok": False,
                    "error": type(error).__name__,
                    "message": str(error),
                },
                recovery_test=recovery_test,
            )

        verifier_error = None
        try:
            verified = bool(spec.verifier(intent.payload, output))
        except Exception as error:  # noqa: BLE001 - verifier is an independent boundary
            verified = False
            verifier_error = {
                "error": type(error).__name__,
                "message": str(error),
            }

        evidence_payload = {
            "intent": asdict(intent),
            "grant": asdict(grant),
            "capability": spec.name,
            "output": output,
            "execution_seconds": elapsed,
            "verifier": {
                "independent": spec.verifier_independent,
                "name": getattr(
                    spec.verifier,
                    "__qualname__",
                    type(spec.verifier).__name__,
                ),
                "passed": verified,
                "error": verifier_error,
            },
        }
        evidence_path = self.evidence.write(
            job_id,
            attempt,
            "verified-output" if verified else "verification-failure",
            evidence_payload,
        )
        evidence_complete = self.evidence.verify(evidence_path)
        if not verified or not evidence_complete:
            result = {
                "ok": False,
                "verified": verified,
                "evidence_complete": evidence_complete,
                "verifier_error": verifier_error,
            }
            self.store.finish(
                job_id,
                "failed_verification",
                result,
                str(evidence_path),
            )
            self.audit.append(
                "job_failed_verification",
                {"job_id": job_id, **result},
            )
            self.store.record(
                False,
                evidence_complete,
                recovery_test,
                spec.verifier_independent,
            )
            return job_id

        state_version = None
        if spec.reducer is not None:
            try:
                current = self.store.get_state(spec.name) or {}
                updated = spec.reducer(current, output)
                state_version = self.store.set_state(spec.name, updated)
            except Exception as error:  # noqa: BLE001 - do not replay side effects after verify
                result = {
                    "ok": False,
                    "verified": True,
                    "error": "state_update_failed",
                    "message": str(error),
                }
                failure_path = self.evidence.write(
                    job_id,
                    attempt,
                    "state-update-failure",
                    {
                        "output_evidence": str(evidence_path),
                        "state_update_error": result,
                    },
                )
                self.store.finish(
                    job_id,
                    "state_update_failed",
                    result,
                    str(failure_path),
                )
                self.audit.append(
                    "job_state_update_failed",
                    {"job_id": job_id, **result},
                )
                self.store.record(
                    False,
                    self.evidence.verify(failure_path),
                    recovery_test,
                    spec.verifier_independent,
                )
                return job_id

        evidence_record = json.loads(evidence_path.read_text(encoding="utf-8"))
        result = {
            "ok": True,
            "verified": True,
            "evidence_sha256": evidence_record["sha256"],
            "state_version": state_version,
            "output": output,
        }
        self.store.finish(job_id, "verified", result, str(evidence_path))
        self.audit.append("job_verified", {"job_id": job_id, **result})
        self.store.record(
            True,
            True,
            recovery_test,
            spec.verifier_independent,
        )
        return job_id

    def run_forever(self, poll_seconds: float = 1.0) -> None:
        if poll_seconds < 0:
            raise ValueError("poll_seconds must be non-negative")
        while True:
            if self.run_once() is None:
                time.sleep(poll_seconds)


def echo_verifier(payload: Json, output: Json) -> bool:
    return output == {"echo": payload}


def echo_reducer(current: Json, output: Json) -> Json:
    return {
        "verified_runs": int(current.get("verified_runs", 0)) + 1,
        "last_output": output,
    }
