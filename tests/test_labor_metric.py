import math

import pytest

from centinal26.labor_metric import LaborEvent, summarize


def event(event_id: str, **kwargs: float) -> LaborEvent:
    return LaborEvent(event_id, evidence_refs=(f"fixture:{event_id}",), **kwargs)


def test_summarize_counts_referenced_labor_effects() -> None:
    summary = summarize(
        [
            event(
                "worker-self-recovery",
                manual_actions_eliminated=4,
                recurring_decisions_automated=2,
                failure_classes_auto_recovered=1,
                minutes_saved=45,
                external_actions_required=1,
            ),
            event(
                "goal-ledger-routing",
                manual_actions_eliminated=3,
                recurring_decisions_automated=3,
                minutes_saved=15,
            ),
        ]
    )

    assert summary.unique_events == 2
    assert summary.manual_actions_eliminated == 7
    assert summary.recurring_decisions_automated == 5
    assert summary.failure_classes_auto_recovered == 1
    assert summary.minutes_saved == 60
    assert summary.hours_saved == 1
    assert summary.external_actions_required == 1
    assert summary.intervention_delta == 6


def test_identical_event_replay_is_idempotent() -> None:
    item = event("same", manual_actions_eliminated=2, minutes_saved=5)
    summary = summarize([item, item])
    assert summary.unique_events == 1
    assert summary.manual_actions_eliminated == 2
    assert summary.minutes_saved == 5


def test_conflicting_duplicate_identity_fails_closed() -> None:
    with pytest.raises(ValueError, match="conflicting labor event identity"):
        summarize(
            [
                event("same", manual_actions_eliminated=1),
                event("same", manual_actions_eliminated=2),
            ]
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"manual_actions_eliminated": -1},
        {"recurring_decisions_automated": -1},
        {"failure_classes_auto_recovered": -1},
        {"minutes_saved": -0.1},
        {"external_actions_required": -1},
    ],
)
def test_negative_claims_are_rejected(kwargs: dict[str, int | float]) -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        event("invalid", **kwargs)


def test_empty_event_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="event_id must be non-empty"):
        LaborEvent("   ", evidence_refs=("fixture:empty-id",))


def test_missing_evidence_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires non-empty evidence_refs"):
        LaborEvent("unsupported", evidence_refs=())


def test_blank_evidence_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires non-empty evidence_refs"):
        LaborEvent("unsupported", evidence_refs=(" ",))


def test_mutable_evidence_reference_container_is_rejected() -> None:
    with pytest.raises(TypeError, match="evidence_refs must be an immutable tuple"):
        LaborEvent("mutable", evidence_refs=["fixture:mutable"])  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_non_finite_time_claims_are_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="minutes_saved must be finite"):
        event("bad-time", minutes_saved=value)


def test_boolean_count_is_rejected() -> None:
    with pytest.raises(TypeError, match="count metrics must be integers"):
        LaborEvent(
            "bad-count",
            evidence_refs=("fixture:bad-count",),
            manual_actions_eliminated=True,
        )
