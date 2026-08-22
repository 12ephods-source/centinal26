import pytest

from centinal26.labor_metric import LaborEvent, summarize


def test_summarize_counts_verified_labor_effects() -> None:
    summary = summarize(
        [
            LaborEvent(
                "worker-self-recovery",
                manual_actions_eliminated=4,
                recurring_decisions_automated=2,
                failure_classes_auto_recovered=1,
                minutes_saved=45,
                external_actions_required=1,
            ),
            LaborEvent(
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
    event = LaborEvent("same", manual_actions_eliminated=2, minutes_saved=5)
    summary = summarize([event, event])
    assert summary.unique_events == 1
    assert summary.manual_actions_eliminated == 2
    assert summary.minutes_saved == 5


def test_conflicting_duplicate_identity_fails_closed() -> None:
    with pytest.raises(ValueError, match="conflicting labor event identity"):
        summarize(
            [
                LaborEvent("same", manual_actions_eliminated=1),
                LaborEvent("same", manual_actions_eliminated=2),
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
        LaborEvent("invalid", **kwargs)


def test_empty_event_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="event_id must be non-empty"):
        LaborEvent("   ")
