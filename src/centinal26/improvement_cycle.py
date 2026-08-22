from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from frost_core.improvement_controller import (
    CanonicalImprovementState,
    ImprovementController,
    WorkCandidate,
)

from .advance import (
    AUTO_SAFE,
    EFFECT_PROTOCOL,
    AdvanceReport,
    _authorization_mode,
    _record_blocker_once,
    _run_task,
    _task_payload,
    build_advance_engine,
)
from .event_state import (
    TERMINAL_TASK_STATES,
    EventStore,
    derive_ready_tasks,
    rebuild_state,
)
from .frost_cli import event_store, state_home


def _metric(task: dict[str, Any], name: str) -> float:
    value = task.get(name, 0.0)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _candidate(task_id: str, task: dict[str, Any]) -> WorkCandidate:
    capability = task.get("capability")
    return WorkCandidate(
        candidate_id=task_id,
        capability=capability if isinstance(capability, str) else "",
        expected_value=_metric(task, "expected_value"),
        risk_reduction=_metric(task, "risk_reduction"),
        dependency_unlock=_metric(task, "dependency_unlock"),
        human_labor_reduction=_metric(task, "human_labor_reduction"),
        execution_cost=_metric(task, "execution_cost"),
        execution_risk=_metric(task, "execution_risk"),
    )


def _rank_runnable(
    runnable: list[tuple[str, str]],
    tasks: dict[str, dict[str, Any]],
) -> list[tuple[str, str]]:
    authorization_by_id = dict(runnable)
    candidates = [_candidate(task_id, tasks[task_id]) for task_id, _ in runnable]
    ranked = ImprovementController.rank(candidates, CanonicalImprovementState())
    return [
        (item.candidate.candidate_id, authorization_by_id[item.candidate.candidate_id])
        for item in ranked
    ]


def advance_ranked_until_idle(
    store: EventStore,
    *,
    authorize: bool = False,
    max_tasks: int = 100,
    authorization_modes: dict[str, str] | None = None,
) -> AdvanceReport:
    """Advance canonical tasks using improvement-value ranking.

    Selection authority is intentionally separate from execution authority. This
    function only reorders tasks that the existing advance engine has already
    determined to be dependency-ready, capability-registered, independently
    verifiable, and authorized. Execution, evidence capture, and verification
    remain delegated to the existing bounded runtime.
    """

    if max_tasks < 1:
        raise ValueError("max_tasks must be positive")
    if max_tasks > 1000:
        raise ValueError("max_tasks may not exceed 1000")
    if not store.verify_chain():
        raise ValueError("refusing advance because the event chain is invalid")

    runtime = build_advance_engine(state_home())
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

            mode = _authorization_mode(
                capability,
                authorization_modes,
                task=task,
            )
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
                    "capability policy or task provenance requires explicit authorization",
                )
                continue
            try:
                _task_payload(task)
            except TypeError as error:
                blockers[task_id] = "INVALID_TASK_INPUT"
                _record_blocker_once(
                    store,
                    state,
                    task_id,
                    "INVALID_TASK_INPUT",
                    str(error),
                )
                continue

            authorization_source = (
                "explicit_improvement_cycle" if authorize else "capability_policy_auto_safe"
            )
            runnable.append((task_id, authorization_source))

        report.blocked.update(blockers)
        if not runnable:
            break

        ranked = _rank_runnable(runnable, state.tasks)
        task_id, authorization_source = ranked[0]
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


@dataclass(frozen=True)
class CycleResult:
    authorize: bool
    max_tasks: int
    report: dict[str, Any]


def run_cycle(*, authorize: bool, max_tasks: int) -> CycleResult:
    store = event_store()
    try:
        report = advance_ranked_until_idle(
            store,
            authorize=authorize,
            max_tasks=max_tasks,
        )
        return CycleResult(
            authorize=authorize,
            max_tasks=max_tasks,
            report=report.as_dict(),
        )
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m centinal26.improvement_cycle",
        description=(
            "Rank dependency-ready canonical work with the Frost improvement "
            "controller, then execute only through the existing bounded advance runtime."
        ),
    )
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--max-tasks", type=int, default=100)
    args = parser.parse_args()
    try:
        result = run_cycle(authorize=args.authorize, max_tasks=args.max_tasks)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
