from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .core import AuditLog, Grant
from .event_state import (
    TERMINAL_TASK_STATES,
    EventStore,
    ProjectState,
    derive_ready_tasks,
    rebuild_state,
)
from .pipeline import (
    AutomatedEngine,
    CapabilitySpec,
    EvidenceStore,
    Intent,
    RuntimeStore,
    canonical_sha256,
    echo_reducer,
    echo_verifier,
)

AUTO_SAFE = "AUTO_SAFE"
EXPLICIT = "EXPLICIT"
EFFECT_PROTOCOL = "EFFECT_PROTOCOL"
VALID_AUTHORIZATION_MODES = {AUTO_SAFE, EXPLICIT, EFFECT_PROTOCOL}
DEFAULT_AUTHORIZATION_MODES = {"system.echo": AUTO_SAFE}


@dataclass
class AdvanceReport:
    executed: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    blocked: dict[str, str] = field(default_factory=dict)
    stop_reason: str = "IDLE"
    remaining_ready: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "executed": self.executed,
            "completed": self.completed,
            "failed": self.failed,
            "blocked": dict(sorted(self.blocked.items())),
            "stop_reason": self.stop_reason,
            "remaining_ready": self.remaining_ready,
        }


def _echo(data: dict[str, Any]) -> dict[str, Any]:
    return {"echo": data}


def build_advance_engine(home: Path) -> AutomatedEngine:
    runtime = AutomatedEngine(
        RuntimeStore(home / "advance.sqlite3"),
        AuditLog(home / "advance-audit.jsonl"),
        EvidenceStore(home / "advance-evidence"),
    )
    runtime.register(
        CapabilitySpec(
            name="system.echo",
            executor=_echo,
            verifier=echo_verifier,
            reducer=echo_reducer,
            verifier_independent=True,
        )
    )
    return runtime


def _grant(capability: str) -> Grant:
    return Grant(
        grant_id=str(uuid.uuid4()),
        capability=capability,
        expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
    )


def _blocker_id(task_id: str, reason: str) -> str:
    digest = hashlib.sha256(f"{task_id}\0{reason}".encode()).hexdigest()[:24]
    return f"blocker:{digest}"


def _record_blocker_once(
    store: EventStore,
    state: ProjectState,
    task_id: str,
    reason: str,
    detail: str,
) -> None:
    blocker_id = _blocker_id(task_id, reason)
    if blocker_id in state.blockers:
        return
    store.append(
        "BLOCKER_RECORDED",
        {
            "blocker_id": blocker_id,
            "task_id": task_id,
            "reason": reason,
            "detail": detail,
        },
        entity_id=blocker_id,
    )


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("input", task.get("payload", {}))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise TypeError("task input/payload must be an object")
    return payload


def _deterministic_intent(task_id: str, capability: str, payload: dict[str, Any]) -> Intent:
    return Intent(
        capability=capability,
        payload=payload,
        actor="event-state-advance",
        constraints={"task_id": task_id},
        intent_id=task_id,
        created_at="1970-01-01T00:00:00+00:00",
    )


def _job_row(runtime: AutomatedEngine, job_id: str):
    row = runtime.store.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"advance job disappeared: {job_id}")
    return row


def _result_digest(row) -> str | None:
    if row["result"] is None:
        return None
    return canonical_sha256(json.loads(row["result"]))


def _authorization_mode(
    capability: str,
    authorization_modes: dict[str, str] | None,
) -> str:
    mode = (authorization_modes or {}).get(
        capability,
        DEFAULT_AUTHORIZATION_MODES.get(capability, EXPLICIT),
    )
    if mode not in VALID_AUTHORIZATION_MODES:
        raise ValueError(f"invalid authorization mode for {capability}: {mode}")
    return mode


def _run_task(
    store: EventStore,
    runtime: AutomatedEngine,
    task_id: str,
    task: dict[str, Any],
    *,
    authorization_source: str,
) -> tuple[bool, str]:
    capability = str(task["capability"])
    payload = _task_payload(task)
    grant = _grant(capability)
    intent = _deterministic_intent(task_id, capability, payload)

    if task.get("status") != "READY":
        store.append(
            "TASK_READY",
            {"task_id": task_id, "capability": capability},
            entity_id=task_id,
        )
    store.append(
        "TASK_AUTHORIZED",
        {
            "task_id": task_id,
            "capability": capability,
            "grant_id": grant.grant_id,
            "expires_at": grant.expires_at,
            "authorization_source": authorization_source,
        },
        entity_id=task_id,
    )

    job_id = runtime.submit(intent, grant, idempotency_key=f"event-task:{task_id}")
    store.append(
        "TASK_STARTED",
        {"task_id": task_id, "job_id": job_id, "capability": capability},
        entity_id=task_id,
    )

    while True:
        row = _job_row(runtime, job_id)
        if row["state"] not in {"queued", "running"}:
            break
        executed_job = runtime.run_once()
        if executed_job is None:
            raise RuntimeError(f"advance runtime could not execute queued task: {task_id}")
        if executed_job != job_id:
            raise RuntimeError("advance runtime executed an unrelated queued job")

    row = _job_row(runtime, job_id)
    state = str(row["state"])
    event_payload = {
        "task_id": task_id,
        "job_id": job_id,
        "runtime_state": state,
        "result_sha256": _result_digest(row),
        "evidence_path": row["evidence_path"],
    }

    if state == "verified":
        store.append("TASK_EXECUTED", event_payload, entity_id=task_id)
        store.append(
            "VERIFICATION_PASSED",
            {**event_payload, "verifier_independent": True},
            entity_id=task_id,
        )
        store.append("TASK_COMPLETED", event_payload, entity_id=task_id)
        return True, state

    if state == "failed_verification":
        store.append("TASK_EXECUTED", event_payload, entity_id=task_id)
        store.append("VERIFICATION_FAILED", event_payload, entity_id=task_id)
        return False, state

    store.append("TASK_FAILED", event_payload, entity_id=task_id)
    return False, state


def advance_until_idle(
    store: EventStore,
    runtime: AutomatedEngine,
    *,
    authorize: bool = False,
    max_tasks: int = 100,
    authorization_modes: dict[str, str] | None = None,
) -> AdvanceReport:
    if max_tasks < 1:
        raise ValueError("max_tasks must be positive")
    if not store.verify_chain():
        raise ValueError("refusing advance because the event chain is invalid")

    if authorization_modes is not None:
        for capability, mode in authorization_modes.items():
            if not capability.strip():
                raise ValueError("authorization mode capability name may not be empty")
            if mode not in VALID_AUTHORIZATION_MODES:
                raise ValueError(f"invalid authorization mode for {capability}: {mode}")

    report = AdvanceReport()
    while len(report.executed) < max_tasks:
        state = rebuild_state(store.events())
        ready = derive_ready_tasks(state)
        runnable: list[tuple[str, str]] = []
        blockers: dict[str, str] = {}

        for task_id in ready:
            task = state.tasks[task_id]
            capability = task.get("capability")
            if not isinstance(capability, str) or not capability:
                blockers[task_id] = "NO_CAPABILITY"
                _record_blocker_once(
                    store,
                    state,
                    task_id,
                    "NO_CAPABILITY",
                    "task has no registered capability name",
                )
                continue
            spec = runtime.capabilities.get(capability)
            if spec is None:
                blockers[task_id] = "NO_CAPABILITY"
                _record_blocker_once(
                    store,
                    state,
                    task_id,
                    "NO_CAPABILITY",
                    f"capability is not registered: {capability}",
                )
                continue
            if not spec.verifier_independent:
                blockers[task_id] = "VERIFIER_NOT_INDEPENDENT"
                _record_blocker_once(
                    store,
                    state,
                    task_id,
                    "VERIFIER_NOT_INDEPENDENT",
                    f"capability lacks independent verification: {capability}",
                )
                continue

            mode = _authorization_mode(capability, authorization_modes)
            if mode == EFFECT_PROTOCOL:
                blockers[task_id] = "EFFECT_PROTOCOL_REQUIRED"
                _record_blocker_once(
                    store,
                    state,
                    task_id,
                    "EFFECT_PROTOCOL_REQUIRED",
                    "external-effect capability must use the frost-effect protocol",
                )
                continue
            if not authorize and mode != AUTO_SAFE:
                blockers[task_id] = "APPROVAL_REQUIRED"
                _record_blocker_once(
                    store,
                    state,
                    task_id,
                    "APPROVAL_REQUIRED",
                    "capability policy requires explicit execution authorization",
                )
                continue
            try:
                _task_payload(task)
            except TypeError as error:
                blockers[task_id] = "INVALID_TASK_INPUT"
                _record_blocker_once(store, state, task_id, "INVALID_TASK_INPUT", str(error))
                continue

            authorization_source = (
                "explicit_advance_invocation" if authorize else "capability_policy_auto_safe"
            )
            runnable.append((task_id, authorization_source))

        report.blocked.update(blockers)
        if not runnable:
            break

        task_id, authorization_source = runnable[0]
        state = rebuild_state(store.events())
        task = state.tasks[task_id]
        ok, _runtime_state = _run_task(
            store,
            runtime,
            task_id,
            task,
            authorization_source=authorization_source,
        )
        report.executed.append(task_id)
        if ok:
            report.completed.append(task_id)
        else:
            report.failed.append(task_id)

    state = rebuild_state(store.events())
    report.remaining_ready = derive_ready_tasks(state)
    unfinished = [
        task_id
        for task_id, task in state.tasks.items()
        if task.get("status") not in TERMINAL_TASK_STATES
    ]

    if len(report.executed) >= max_tasks and report.remaining_ready:
        report.stop_reason = "RESOURCE_LIMIT"
    elif report.remaining_ready:
        reasons = {report.blocked.get(task_id) for task_id in report.remaining_ready}
        reasons.discard(None)
        if reasons == {"APPROVAL_REQUIRED"}:
            report.stop_reason = "APPROVAL_REQUIRED"
        elif reasons == {"EFFECT_PROTOCOL_REQUIRED"}:
            report.stop_reason = "EFFECT_PROTOCOL_REQUIRED"
        elif reasons and reasons <= {"NO_CAPABILITY", "VERIFIER_NOT_INDEPENDENT"}:
            report.stop_reason = "NO_CAPABILITY"
        else:
            report.stop_reason = "BLOCKED"
    elif unfinished:
        report.stop_reason = "DEPENDENCY_BLOCKED"
    else:
        report.stop_reason = "COMPLETE"
    return report
