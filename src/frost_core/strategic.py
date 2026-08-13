from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class BranchOption:
    branch_id: str
    success_probability: float
    expected_gain: float
    cost: float
    risk: float
    irreversibility: float
    uncertainty: float
    future_optionality: float

    def __post_init__(self) -> None:
        for name, value in (
            ("success_probability", self.success_probability),
            ("expected_gain", self.expected_gain),
            ("cost", self.cost),
            ("risk", self.risk),
            ("irreversibility", self.irreversibility),
            ("uncertainty", self.uncertainty),
            ("future_optionality", self.future_optionality),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if not self.branch_id.strip():
            raise ValueError("branch_id must not be empty")


@dataclass(frozen=True)
class BranchForecast:
    branch_id: str
    immediate_value: float
    exploration_bonus: float
    optionality_bonus: float
    strategic_score: float


class StrategicBranchForecaster:
    """Rank bounded branches without granting any branch promotion authority."""

    def __init__(self, exploration_weight: float = 0.12, optionality_weight: float = 0.18) -> None:
        if not 0.0 <= exploration_weight <= 1.0:
            raise ValueError("exploration_weight must be in [0, 1]")
        if not 0.0 <= optionality_weight <= 1.0:
            raise ValueError("optionality_weight must be in [0, 1]")
        self.exploration_weight = exploration_weight
        self.optionality_weight = optionality_weight

    def forecast(self, option: BranchOption) -> BranchForecast:
        immediate = (
            option.success_probability * option.expected_gain
            - 0.30 * option.cost
            - 0.35 * option.risk
            - 0.25 * option.irreversibility
        )
        exploration = self.exploration_weight * sqrt(option.uncertainty)
        optionality = self.optionality_weight * option.future_optionality
        score = immediate + exploration + optionality
        return BranchForecast(
            branch_id=option.branch_id,
            immediate_value=round(immediate, 6),
            exploration_bonus=round(exploration, 6),
            optionality_bonus=round(optionality, 6),
            strategic_score=round(score, 6),
        )

    def rank(self, options: list[BranchOption]) -> list[BranchForecast]:
        forecasts = [self.forecast(option) for option in options]
        return sorted(forecasts, key=lambda item: item.strategic_score, reverse=True)
