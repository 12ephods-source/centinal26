"""Deterministic resolver for project questions that do not require user input."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

AUTO_EXECUTE_CLASSES = {"A0", "A1", "A2"}


@dataclass(frozen=True)
class Option:
    option_id: str
    action_class: str
    goal_advancement: float = 0.0
    information_gain: float = 0.0
    dependency_unblocking: float = 0.0
    falsification_value: float = 0.0
    reusable_capability_value: float = 0.0
    execution_cost: float = 0.0
    expected_risk: float = 0.0
    duplication_cost: float = 0.0
    resolvable: bool = True
    authorized: bool = True

    @property
    def score(self) -> float:
        return (
            self.goal_advancement
            + self.information_gain
            + self.dependency_unblocking
            + self.falsification_value
            + self.reusable_capability_value
            - self.execution_cost
            - self.expected_risk
            - self.duplication_cost
        )


@dataclass(frozen=True)
class Resolution:
    question: str
    status: str
    selected_option_id: str | None
    action_class: str | None
    score: float | None
    should_execute: bool
    should_ask_user: bool
    reason: str
    resolved_at_utc: str

    def to_dict(self) -> dict:
        return asdict(self)


def resolve_question(question: str, options: Iterable[Option]) -> Resolution:
    """Choose the highest-value authorized resolvable option or expose a true boundary."""
    candidates = [option for option in options if option.resolvable and option.authorized]
    now = datetime.now(UTC).isoformat()

    if not candidates:
        return Resolution(
            question=question,
            status="BOUNDARY",
            selected_option_id=None,
            action_class=None,
            score=None,
            should_execute=False,
            should_ask_user=True,
            reason="NO_AUTHORIZED_RESOLVABLE_OPTION",
            resolved_at_utc=now,
        )

    selected = max(candidates, key=lambda option: (option.score, option.option_id))
    auto = selected.action_class in AUTO_EXECUTE_CLASSES
    return Resolution(
        question=question,
        status="RESOLVED" if auto else "AUTHORIZATION_BOUNDARY",
        selected_option_id=selected.option_id,
        action_class=selected.action_class,
        score=selected.score,
        should_execute=auto,
        should_ask_user=not auto,
        reason="HIGHEST_ACTION_VALUE" if auto else "SIDE_EFFECT_REQUIRES_EXPLICIT_AUTHORITY",
        resolved_at_utc=now,
    )
