import sys
from importlib import util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "automation"
    / "runtime"
    / "autonomous_question_resolver.py"
)


def load_module():
    module_name = "autonomous_question_resolver"
    spec = util.spec_from_file_location(module_name, MODULE_PATH)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
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


def test_a4_never_auto_executes_from_general_delegation():
    module = load_module()
    result = module.resolve_question(
        "Delete the production state?",
        [module.Option("delete", "A4", goal_advancement=100)],
    )
    assert result.should_execute is False
    assert result.should_ask_user is True
    assert result.reason == "A4_REQUIRES_EXACT_EXPLICIT_AUTHORITY"


def test_exactly_authorized_a3_can_auto_execute():
    module = load_module()
    result = module.resolve_question(
        "Publish the already-authorized project artifact?",
        [
            module.Option(
                "publish",
                "A3",
                goal_advancement=10,
                exact_side_effect_authority=True,
            )
        ],
    )
    assert result.should_execute is True
    assert result.should_ask_user is False
    assert result.reason == "EXACT_A3_AUTHORITY"


def test_platform_confirmation_still_blocks_a3():
    module = load_module()
    result = module.resolve_question(
        "Complete a platform-confirmed side effect?",
        [
            module.Option(
                "confirm",
                "A3",
                goal_advancement=10,
                exact_side_effect_authority=True,
                platform_confirmation_required=True,
            )
        ],
    )
    assert result.should_execute is False
    assert result.reason == "PLATFORM_CONFIRMATION_REQUIRED"


def test_objective_change_is_not_silently_substituted():
    module = load_module()
    result = module.resolve_question(
        "Change the requested project outcome?",
        [module.Option("change-goal", "A2", goal_advancement=20, changes_objective=True)],
    )
    assert result.should_execute is False
    assert result.reason == "OBJECTIVE_CHANGE_REQUIRES_USER"


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


def test_decision_ledger_is_append_only_jsonl(tmp_path):
    module = load_module()
    resolution = module.resolve_question(
        "Pick the bounded action",
        [module.Option("run", "A1", goal_advancement=1)],
    )
    ledger = tmp_path / "decisions.jsonl"
    module.append_decision_ledger(ledger, resolution)
    module.append_decision_ledger(ledger, resolution)
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert '"selected_option_id": "run"' in lines[0]
