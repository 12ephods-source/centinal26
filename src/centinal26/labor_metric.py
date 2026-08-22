from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class LaborEvent:
    """One claimed automation effect with explicit supporting evidence references."""

    event_id: str
    evidence_refs: tuple[str, ...]
    manual_actions_eliminated: int = 0
    recurring_decisions_automated: int = 0
    failure_classes_auto_recovered: int = 0
    minutes_saved: float = 0.0
    external_actions_required: int = 0

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id must be non-empty")
        if not self.evidence_refs or any(
            not isinstance(ref, str) or not ref.strip() for ref in self.evidence_refs
        ):
            raise ValueError("labor event requires non-empty evidence_refs")

        integer_fields = (
            self.manual_actions_eliminated,
            self.recurring_decisions_automated,
            self.failure_classes_auto_recovered,
            self.external_actions_required,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) for value in integer_fields):
            raise TypeError("labor count metrics must be integers")
        if not isinstance(self.minutes_saved, (int, float)) or isinstance(self.minutes_saved, bool):
            raise TypeError("minutes_saved must be numeric")
        if any(value < 0 for value in integer_fields) or self.minutes_saved < 0:
            raise ValueError("labor metrics cannot be negative")
        if not math.isfinite(float(self.minutes_saved)):
            raise ValueError("minutes_saved must be finite")


@dataclass(frozen=True)
class LaborSummary:
    unique_events: int
    manual_actions_eliminated: int
    recurring_decisions_automated: int
    failure_classes_auto_recovered: int
    minutes_saved: float
    external_actions_required: int

    @property
    def hours_saved(self) -> float:
        return self.minutes_saved / 60.0

    @property
    def intervention_delta(self) -> int:
        """Positive means more future manual actions were removed than remain."""

        return self.manual_actions_eliminated - self.external_actions_required


def summarize(events: Iterable[LaborEvent]) -> LaborSummary:
    """Deduplicate by stable event identity and aggregate referenced labor claims.

    This function validates event structure and evidence-reference presence; it does not
    independently establish that referenced evidence proves the claimed labor effect.
    Duplicate identical events are idempotent. Conflicting events sharing an ID fail
    closed instead of silently double-counting or choosing one version.
    """

    by_id: dict[str, LaborEvent] = {}
    for event in events:
        prior = by_id.get(event.event_id)
        if prior is None:
            by_id[event.event_id] = event
        elif prior != event:
            raise ValueError(f"conflicting labor event identity: {event.event_id}")

    values = tuple(by_id.values())
    return LaborSummary(
        unique_events=len(values),
        manual_actions_eliminated=sum(e.manual_actions_eliminated for e in values),
        recurring_decisions_automated=sum(e.recurring_decisions_automated for e in values),
        failure_classes_auto_recovered=sum(e.failure_classes_auto_recovered for e in values),
        minutes_saved=sum(e.minutes_saved for e in values),
        external_actions_required=sum(e.external_actions_required for e in values),
    )
