from importlib import util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "automation"
    / "runtime"
    / "autonomous_question_resolver.py"
)


def load_module():
    spec = util.spec_from_file_location("autonomous_question_resolver", MODULE_PATH)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolvable_a2_question_is_answered_and_executed():
    module = load_module()
    result = module.resolve_question(
        "Which bounded project write should run next?",
        [
            module.Option("low", "A2", goal_advancement=2, execution_cost=1),
            module.Option(
                "high",
                "A2",
                goal_advancement=5,
                dependency_unblocking=3,
                execution_cost=1,
            ),
        ],
    )
    assert result.selected_option_id == "high"
    assert result.should_execute is True
    assert result.should_ask_user is False
    assert result.status == "RESOLVED"


def test_unresolvable_question_surfaces_real_boundary():
    module = load_module()
    result = module.resolve_question(
        "What credential is missing?",
        [module.Option("unknown", "A2", resolvable=False)],
    )
    assert result.should_execute is False
    assert result.should_ask_user is True
    assert result.reason == "NO_AUTHORIZED_RESOLVABLE_OPTION"


def test_a4_never_auto_executes():
    module = load_module()
    result = module.resolve_question(
        "Delete the production state?",
        [module.Option("delete", "A4", goal_advancement=100)],
    )
    assert result.should_execute is False
    assert result.should_ask_user is True
    assert result.status == "AUTHORIZATION_BOUNDARY"


def test_risk_and_cost_reduce_action_value():
    module = load_module()
    result = module.resolve_question(
        "Choose a discriminating test",
        [
            module.Option("expensive", "A1", information_gain=10, execution_cost=9),
            module.Option("cheap", "A1", information_gain=6, execution_cost=1),
        ],
    )
    assert result.selected_option_id == "cheap"
