import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "automation/federation/project_goal_reconciler.py"
spec = importlib.util.spec_from_file_location("project_goal_reconciler", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_explicit_physical_boundary_is_not_promoted():
    prs = [{
        "number": 92,
        "title": "Physical capability",
        "body": "Actual DEVICE_VALIDATED promotion remains contingent on Android/Termux. This PR should remain draft.",
        "draft": True,
        "mergeable": True,
    }]
    result = mod.reconcile(prs)
    assert result["actionable_count"] == 0
    assert result["blocked"][0]["reason"] == "explicit_merge_boundary"


def test_internal_draft_remains_actionable():
    prs = [{
        "number": 5,
        "title": "Internal refactor",
        "body": "Refactor canonical state handling.",
        "draft": True,
        "mergeable": True,
    }]
    result = mod.reconcile(prs)
    assert result["next_action"]["number"] == 5
    assert result["next_action"]["reason"] == "draft_internal_work"


def test_nonmergeable_ready_pr_has_highest_priority():
    prs = [
        {"number": 6, "title": "Ready", "body": "", "draft": False, "mergeable": True},
        {"number": 7, "title": "Conflict", "body": "", "draft": False, "mergeable": False},
    ]
    result = mod.reconcile(prs)
    assert result["next_action"]["number"] == 7
    assert result["next_action"]["reason"] == "repair_mergeability"


def test_external_draft_without_explicit_merge_phrase_is_blocked():
    prs = [{
        "number": 8,
        "title": "Provider bridge",
        "body": "Provider execution boundary requires privileged Base44 transport.",
        "draft": True,
        "mergeable": True,
    }]
    result = mod.reconcile(prs)
    assert result["actionable_count"] == 0
    assert result["blocked"][0]["reason"] == "external_dependency"
