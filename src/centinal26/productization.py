from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


def _require_refs(refs: tuple[str, ...], *, field: str) -> None:
    if not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise ValueError(f"{field} requires non-empty evidence references")


def _require_score(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100")


@dataclass(frozen=True)
class ProductCandidate:
    """Evidence-referenced inputs for deterministic product prioritization.

    Scores are policy inputs, not claims of market truth or realized economic value.
    """

    candidate_id: str
    evidence_refs: tuple[str, ...]
    measurable_value: int
    labor_reduction: int
    validation_strength: int
    mvp_readiness: int
    implementation_cost: int
    risk: int
    mvp_complete: bool = False
    validation_gate_passed: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id must be non-empty")
        _require_refs(self.evidence_refs, field="product candidate")
        for name, value in (
            ("measurable_value", self.measurable_value),
            ("labor_reduction", self.labor_reduction),
            ("validation_strength", self.validation_strength),
            ("mvp_readiness", self.mvp_readiness),
            ("implementation_cost", self.implementation_cost),
            ("risk", self.risk),
        ):
            _require_score(name, value)
        if type(self.mvp_complete) is not bool or type(self.validation_gate_passed) is not bool:
            raise TypeError("MVP and validation gate fields must be booleans")
        if self.validation_gate_passed and not self.mvp_complete:
            raise ValueError("validation gate cannot pass before MVP completion")

    @property
    def priority_score(self) -> int:
        """Return a bounded policy score; higher means investigate/build earlier."""

        return (
            30 * self.measurable_value
            + 20 * self.labor_reduction
            + 20 * self.validation_strength
            + 20 * self.mvp_readiness
            - 5 * self.implementation_cost
            - 5 * self.risk
        )

    @property
    def product_state(self) -> str:
        if self.validation_gate_passed:
            return "VALIDATED_MVP"
        if self.mvp_complete:
            return "MVP_COMPLETE_UNVALIDATED"
        return "CANDIDATE"


def rank_candidates(candidates: Iterable[ProductCandidate]) -> tuple[ProductCandidate, ...]:
    """Deduplicate candidates and rank by deterministic policy score.

    Identical replay is idempotent. Conflicting records with one candidate ID fail
    closed. Ranking does not establish market demand, profitability, or revenue.
    """

    by_id: dict[str, ProductCandidate] = {}
    for candidate in candidates:
        prior = by_id.get(candidate.candidate_id)
        if prior is None:
            by_id[candidate.candidate_id] = candidate
        elif prior != candidate:
            raise ValueError(f"conflicting product candidate identity: {candidate.candidate_id}")
    return tuple(sorted(by_id.values(), key=lambda item: (-item.priority_score, item.candidate_id)))


@dataclass(frozen=True)
class RevenueTransaction:
    """One transaction record eligible for realized-revenue accounting only if verified."""

    transaction_id: str
    candidate_id: str
    currency: str
    amount_minor: int
    evidence_refs: tuple[str, ...]
    settled: bool
    independently_verified: bool

    def __post_init__(self) -> None:
        if not self.transaction_id.strip() or not self.candidate_id.strip():
            raise ValueError("transaction_id and candidate_id must be non-empty")
        if len(self.currency) != 3 or not self.currency.isalpha() or self.currency != self.currency.upper():
            raise ValueError("currency must be a three-letter uppercase code")
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            raise TypeError("amount_minor must be an integer")
        if self.amount_minor < 0:
            raise ValueError("amount_minor cannot be negative")
        if type(self.settled) is not bool or type(self.independently_verified) is not bool:
            raise TypeError("transaction state fields must be booleans")
        _require_refs(self.evidence_refs, field="revenue transaction")


def realized_revenue(transactions: Iterable[RevenueTransaction]) -> dict[str, int]:
    """Sum only settled + independently verified transaction evidence by currency.

    This function cannot verify a payment provider itself. The
    ``independently_verified`` flag must be supplied only after an external verifier has
    checked the referenced transaction evidence. Unverified or unsettled records count
    as zero realized revenue.
    """

    by_id: dict[str, RevenueTransaction] = {}
    for transaction in transactions:
        prior = by_id.get(transaction.transaction_id)
        if prior is None:
            by_id[transaction.transaction_id] = transaction
        elif prior != transaction:
            raise ValueError(f"conflicting transaction identity: {transaction.transaction_id}")

    totals: dict[str, int] = {}
    for transaction in by_id.values():
        if transaction.settled and transaction.independently_verified:
            totals[transaction.currency] = totals.get(transaction.currency, 0) + transaction.amount_minor
    return dict(sorted(totals.items()))
