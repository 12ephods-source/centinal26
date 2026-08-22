"""Selection-rule checks for the candidate FToE L1 protecting architecture.

The discrete selector is not claimed to protect I by itself. I must already be
a protected/pNGB direction. The selector only constrains the sole spurion that
is allowed to break that protection.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CyclicSelector:
    order: int
    spurion_charge: int = 1

    def invariant_power(self, power: int) -> bool:
        return (power * self.spurion_charge) % self.order == 0

    def first_positive_invariant_power(self, limit: int = 64) -> int | None:
        for power in range(1, limit + 1):
            if self.invariant_power(power):
                return power
        return None


def minimal_selector_for_first_power(target_power: int) -> CyclicSelector:
    """Find the smallest Z_N with unit spurion charge first neutral at target_power."""
    if target_power < 1:
        raise ValueError("target_power must be positive")
    for order in range(2, target_power + 2):
        selector = CyclicSelector(order=order)
        if selector.first_positive_invariant_power(target_power) == target_power:
            return selector
    raise RuntimeError("no cyclic selector found")


def dimension_13_candidate_allowed(selector: CyclicSelector) -> bool:
    """Candidate: protected mass structure * S^9 * Sigma^2 / M_P^9."""
    return selector.invariant_power(9)


def lower_breaking_powers_forbidden(selector: CyclicSelector) -> bool:
    return all(not selector.invariant_power(power) for power in range(1, 9))


def scalar_only_discrete_anomaly_status(*, chiral_fermions_charged: bool) -> str:
    """Return the perturbative mixed-anomaly gate for the selector."""
    return "REVIEW" if chiral_fermions_charged else "PASS_CONDITIONAL"
