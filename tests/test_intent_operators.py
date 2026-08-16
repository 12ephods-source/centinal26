from centinal26.intent_operators import IntentOperator, classify_intent
from centinal26.reconciliation import CompletionLevel, ProjectState, ReconciliationEvent, reconcile


def test_literal_policy_operators_are_deterministic():
    cases = {
        "Proceed": IntentOperator.EXECUTE,
        "project state": IntentOperator.STATE,
        "verify": IntentOperator.VERIFY,
        "refute that": IntentOperator.ADVERSARIAL,
        "automate this": IntentOperator.AUTOMATE,
        "combine these": IntentOperator.COMPRESS,
        "recover it": IntentOperator.RECOVER,
        "fix everything": IntentOperator.FIX,
        "improve": IntentOperator.IMPROVE,
        "checkpoint": IntentOperator.CHECKPOINT,
    }
    for text, expected in cases.items():
        match = classify_intent(text)
        assert match is not None
        assert match.operator == expected
        assert match.confidence >= 0.70


def test_unknown_prose_does_not_invent_operator():
    assert classify_intent("derive the spectrum for this Hamiltonian") is None


def test_embedded_operator_is_not_full_authorization():
    match = classify_intent("Could you explain whether we should proceed after review?")
    assert match is not None
    assert match.operator == IntentOperator.EXECUTE
    assert match.confidence < 1.0


def test_reconciliation_tracks_blockers_and_friction():
    state = ProjectState(project_id="centinal26")
    event = ReconciliationEvent.create(
        project_id="centinal26",
        intent=IntentOperator.EXECUTE,
        action="deploy provider bridge",
        result="BLOCKED:NOT_AUTHORIZED",
        evidence=("proof:abc",),
    )
    reconcile(state, event)
    assert state.last_event_id == event.event_id
    assert state.blockers == ["NOT_AUTHORIZED"]
    assert state.friction["EXECUTE"] == 1
    assert len(state.snapshot()["state_digest"]) == 64


def test_completion_cannot_regress():
    state = ProjectState(project_id="centinal26")
    state.promote("intent-operators", CompletionLevel.TESTED)
    try:
        state.promote("intent-operators", CompletionLevel.IMPLEMENTED)
    except ValueError:
        pass
    else:
        raise AssertionError("completion regression must be rejected")
