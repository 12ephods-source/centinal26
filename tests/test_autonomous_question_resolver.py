from automation.runtime.autonomous_question_resolver import Option, resolve_question


def test_resolvable_a2_question_is_answered_and_executed():
    result = resolve_question(
        "Which bounded project write should run next?",
        [
            Option("low", "A2", goal_advancement=2, execution_cost=1),
            Option("high", "A2", goal_advancement=5, dependency_unblocking=3, execution_cost=1),
        ],
    )
    assert result.selected_option_id == "high"
    assert result.should_execute is True
    assert result.should_ask_user is False
    assert result.status == "RESOLVED"


def test_unresolvable_question_surfaces_real_boundary():
    result = resolve_question(
        "What credential is missing?",
        [Option("unknown", "A2", resolvable=False)],
    )
    assert result.should_execute is False
    assert result.should_ask_user is True
    assert result.reason == "NO_AUTHORIZED_RESOLVABLE_OPTION"


def test_a4_never_auto_executes():
    result = resolve_question(
        "Delete the production state?",
        [Option("delete", "A4", goal_advancement=100)],
    )
    assert result.should_execute is False
    assert result.should_ask_user is True
    assert result.status == "AUTHORIZATION_BOUNDARY"


def test_risk_and_cost_reduce_action_value():
    result = resolve_question(
        "Choose a discriminating test",
        [
            Option("expensive", "A1", information_gain=10, execution_cost=9),
            Option("cheap", "A1", information_gain=6, execution_cost=1),
        ],
    )
    assert result.selected_option_id == "cheap"
