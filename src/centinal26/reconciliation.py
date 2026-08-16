from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Iterable

from .control_plane import canonical_sha256
from .intent_operators import IntentOperator


class ArtifactStatus(StrEnum):
    CANONICAL = "CANONICAL"
    COMPATIBLE_MODULE = "COMPATIBLE_MODULE"
    EXPERIMENTAL = "EXPERIMENTAL"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class CompletionLevel(StrEnum):
    PROPOSED = "PROPOSED"
    IMPLEMENTED = "IMPLEMENTED"
    EXECUTED = "EXECUTED"
    TESTED = "TESTED"
    INDEPENDENTLY_VERIFIED = "INDEPENDENTLY_VERIFIED"
    ADVERSARIALLY_REVIEWED = "ADVERSARIALLY_REVIEWED"
    PROMOTED = "PROMOTED"


@dataclass(frozen=True)
class ReconciliationEvent:
    event_id: str
    project_id: str
    intent: IntentOperator
    action: str
    result: str
    evidence: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    parent_event: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def create(cls, *, project_id: str, intent: IntentOperator, action: str,
               result: str, evidence: Iterable[str] = (), artifacts: Iterable[str] = (),
               parent_event: str | None = None) -> "ReconciliationEvent":
        seed = {
            "project_id": project_id,
            "intent": intent.value,
            "action": action,
            "result": result,
            "evidence": sorted(evidence),
            "artifacts": sorted(artifacts),
            "parent_event": parent_event,
        }
        return cls(
            event_id=f"evt_{canonical_sha256(seed)[:20]}",
            project_id=project_id,
            intent=intent,
            action=action,
            result=result,
            evidence=tuple(sorted(evidence)),
            artifacts=tuple(sorted(artifacts)),
            parent_event=parent_event,
        )


@dataclass
class ProjectState:
    project_id: str
    objective: str = ""
    phase: str = ""
    blockers: list[str] = field(default_factory=list)
    pending_actions: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    canonical_artifacts: dict[str, str] = field(default_factory=dict)
    completion: dict[str, CompletionLevel] = field(default_factory=dict)
    friction: dict[str, int] = field(default_factory=dict)
    last_event_id: str | None = None

    def record_friction(self, operator: IntentOperator) -> None:
        key = operator.value
        self.friction[key] = self.friction.get(key, 0) + 1

    def promote(self, subject: str, level: CompletionLevel) -> None:
        order = list(CompletionLevel)
        current = self.completion.get(subject, CompletionLevel.PROPOSED)
        if order.index(level) < order.index(current):
            raise ValueError("completion level cannot regress")
        self.completion[subject] = level

    def snapshot(self) -> dict[str, Any]:
        data = asdict(self)
        data["completion"] = {k: v.value for k, v in self.completion.items()}
        data["state_digest"] = canonical_sha256(data)
        return data


def reconcile(state: ProjectState, event: ReconciliationEvent) -> ProjectState:
    if event.project_id != state.project_id:
        raise ValueError("event project does not match state project")
    state.last_event_id = event.event_id
    state.record_friction(event.intent)
    if event.result.startswith("BLOCKED:"):
        blocker = event.result.removeprefix("BLOCKED:").strip()
        if blocker and blocker not in state.blockers:
            state.blockers.append(blocker)
    elif event.result.startswith("FAILED:"):
        failure = event.result.removeprefix("FAILED:").strip()
        if failure and failure not in state.failures:
            state.failures.append(failure)
    return state
