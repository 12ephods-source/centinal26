from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class IntentOperator(StrEnum):
    EXECUTE = "EXECUTE"
    STATE = "STATE"
    RECONCILE = "RECONCILE"
    VERIFY = "VERIFY"
    ADVERSARIAL = "ADVERSARIAL"
    AUTOMATE = "AUTOMATE"
    COMPRESS = "COMPRESS"
    RECOVER = "RECOVER"
    FIX = "FIX"
    IMPROVE = "IMPROVE"
    CHECKPOINT = "CHECKPOINT"


@dataclass(frozen=True)
class IntentMatch:
    operator: IntentOperator
    confidence: float
    matched_phrase: str


_PHRASES: dict[IntentOperator, tuple[str, ...]] = {
    IntentOperator.EXECUTE: ("proceed", "continue", "implement", "run it", "execute"),
    IntentOperator.STATE: ("project state", "current state", "where are we", "status"),
    IntentOperator.RECONCILE: ("reconcile", "what happened", "reconstruct history"),
    IntentOperator.VERIFY: (
        "verify",
        "validate",
        "check it",
        "test it",
        "was this actually accomplished",
    ),
    IntentOperator.ADVERSARIAL: ("refute", "criticize", "critique", "opposite opinion"),
    IntentOperator.AUTOMATE: ("automate", "run automatically", "make this reusable"),
    IntentOperator.COMPRESS: (
        "combine",
        "consolidate",
        "canonicalize",
        "extract reusable machinery",
    ),
    IntentOperator.RECOVER: ("recover", "restore", "what happened to that file"),
    IntentOperator.FIX: ("fix", "repair", "fix everything"),
    IntentOperator.IMPROVE: ("improve", "suggest improvements", "optimize"),
    IntentOperator.CHECKPOINT: ("checkpoint", "save state", "preserve state"),
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().strip())


def classify_intent(text: str) -> IntentMatch | None:
    normalized = _normalize(text)
    if not normalized:
        return None
    candidates: list[IntentMatch] = []
    for operator, phrases in _PHRASES.items():
        for phrase in phrases:
            if normalized == phrase:
                candidates.append(IntentMatch(operator, 1.0, phrase))
            elif phrase in normalized:
                candidates.append(IntentMatch(operator, 0.70, phrase))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.confidence, len(item.matched_phrase)))


def supported_operators() -> Iterable[IntentOperator]:
    return tuple(IntentOperator)
