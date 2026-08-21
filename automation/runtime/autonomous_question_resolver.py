"""Deterministic resolver for project questions that do not require user input."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

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
    exact_side_effect_authority: bool = False
    platform_confirmation_required: bool = False
    changes_objective: bool = False

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


def _is_auto_executable(option: Option) -> tuple[bool, str]:
    if option.changes_objective:
        return False, "OBJECTIVE_CHANGE_REQUIRES_USER"
    if option.platform_confirmation_required:
        return False, "PLATFORM_CONFIRMATION_REQUIRED"
    if option.action_class in AUTO_EXECUTE_CLASSES:
        return True, "HIGHEST_ACTION_VALUE"
    if option.action_class == "A3" and option.exact_side_effect_authority:
        return True, "EXACT_A3_AUTHORITY"
    if option.action_class == "A3":
        return False, "A3_REQUIRES_EXACT_AUTHORITY"
    if option.action_class == "A4":
        return False, "A4_REQUIRES_EXACT_EXPLICIT_AUTHORITY"
    return False, "UNKNOWN_ACTION_CLASS"


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
    auto, reason = _is_auto_executable(selected)
    return Resolution(
        question=question,
        status="RESOLVED" if auto else "BOUNDARY",
        selected_option_id=selected.option_id,
        action_class=selected.action_class,
        score=selected.score,
        should_execute=auto,
        should_ask_user=not auto,
        reason=reason,
        resolved_at_utc=now,
    )


def append_decision_ledger(path: str | Path, resolution: Resolution) -> None:
    """Append one immutable JSONL decision record for provenance."""
    ledger = Path(path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(resolution.to_dict(), sort_keys=True) + "\n")
