import pytest

from centinal26.productization import (
    ProductCandidate,
    RevenueTransaction,
    rank_candidates,
    realized_revenue,
)


def candidate(
    candidate_id: str,
    *,
    measurable_value: int = 50,
    labor_reduction: int = 50,
    validation_strength: int = 50,
    mvp_readiness: int = 50,
    implementation_cost: int = 50,
    risk: int = 50,
    mvp_complete: bool = False,
    validation_gate_passed: bool = False,
) -> ProductCandidate:
    return ProductCandidate(
        candidate_id=candidate_id,
        evidence_refs=(f"fixture:{candidate_id}",),
        measurable_value=measurable_value,
        labor_reduction=labor_reduction,
        validation_strength=validation_strength,
        mvp_readiness=mvp_readiness,
        implementation_cost=implementation_cost,
        risk=risk,
        mvp_complete=mvp_complete,
        validation_gate_passed=validation_gate_passed,
    )


def transaction(
    transaction_id: str,
    *,
    amount_minor: int = 1000,
    settled: bool = True,
    independently_verified: bool = True,
    currency: str = "USD",
) -> RevenueTransaction:
    return RevenueTransaction(
        transaction_id=transaction_id,
        candidate_id="test-a-theory",
        currency=currency,
        amount_minor=amount_minor,
        evidence_refs=(f"fixture:{transaction_id}",),
        settled=settled,
        independently_verified=independently_verified,
    )


def test_candidate_ranking_is_deterministic() -> None:
    high = candidate("high", measurable_value=90, labor_reduction=80, mvp_readiness=80)
    low = candidate("low", measurable_value=20, labor_reduction=20, mvp_readiness=20)
    ranked = rank_candidates([low, high])
    assert [item.candidate_id for item in ranked] == ["high", "low"]
    assert ranked[0].priority_score > ranked[1].priority_score


def test_identical_candidate_replay_is_idempotent() -> None:
    item = candidate("same")
    assert rank_candidates([item, item]) == (item,)


def test_conflicting_candidate_identity_fails_closed() -> None:
    with pytest.raises(ValueError, match="conflicting product candidate identity"):
        rank_candidates([candidate("same", measurable_value=10), candidate("same", measurable_value=20)])


def test_candidate_requires_evidence_reference() -> None:
    with pytest.raises(ValueError, match="requires non-empty evidence references"):
        ProductCandidate(
            candidate_id="unsupported",
            evidence_refs=(),
            measurable_value=1,
            labor_reduction=1,
            validation_strength=1,
            mvp_readiness=1,
            implementation_cost=1,
            risk=1,
        )


@pytest.mark.parametrize("value", [-1, 101])
def test_candidate_score_bounds_fail_closed(value: int) -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        candidate("bad-score", measurable_value=value)


def test_boolean_score_is_rejected() -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        candidate("bad-score", measurable_value=True)


def test_validation_cannot_pass_before_mvp_completion() -> None:
    with pytest.raises(ValueError, match="cannot pass before MVP completion"):
        candidate("invalid-state", validation_gate_passed=True)


def test_product_state_requires_separate_mvp_and_validation_gates() -> None:
    assert candidate("planned").product_state == "CANDIDATE"
    assert candidate("mvp", mvp_complete=True).product_state == "MVP_COMPLETE_UNVALIDATED"
    assert (
        candidate("validated", mvp_complete=True, validation_gate_passed=True).product_state
        == "VALIDATED_MVP"
    )


def test_realized_revenue_counts_only_settled_verified_transactions() -> None:
    totals = realized_revenue(
        [
            transaction("verified", amount_minor=1500),
            transaction("unsettled", amount_minor=9000, settled=False),
            transaction("unverified", amount_minor=7000, independently_verified=False),
            transaction("mxn", amount_minor=2500, currency="MXN"),
        ]
    )
    assert totals == {"MXN": 2500, "USD": 1500}


def test_transaction_replay_is_idempotent() -> None:
    item = transaction("same", amount_minor=1200)
    assert realized_revenue([item, item]) == {"USD": 1200}


def test_conflicting_transaction_identity_fails_closed() -> None:
    with pytest.raises(ValueError, match="conflicting transaction identity"):
        realized_revenue([transaction("same", amount_minor=100), transaction("same", amount_minor=200)])


def test_negative_transaction_amount_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        transaction("negative", amount_minor=-1)


def test_invalid_currency_is_rejected() -> None:
    with pytest.raises(ValueError, match="three-letter uppercase"):
        transaction("currency", currency="usd")


def test_missing_transaction_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires non-empty evidence references"):
        RevenueTransaction(
            transaction_id="unsupported",
            candidate_id="test-a-theory",
            currency="USD",
            amount_minor=100,
            evidence_refs=(),
            settled=True,
            independently_verified=True,
        )
