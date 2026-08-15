import runpy
from pathlib import Path

MODULE = runpy.run_path(Path(__file__).resolve().parents[1] / "scripts" / "agent_fleet_review_gate.py")
route_branch = MODULE["route_branch"]
route_snapshot = MODULE["route_snapshot"]


def row(branch, state, *, open_prs=None):
    return {"branch": branch, "head_sha": "a" * 40, "state": state, "open_prs": open_prs or []}


def snapshot(*rows):
    return {
        "schema": "frost-agent-fleet-qualification/1.0",
        "repository": "12ephods-source/centinal26",
        "base": "main",
        "branches": list(rows),
    }


def test_subsumed_and_superseded_never_enter_deep_review():
    assert route_branch(row("agent/a", "SUBSUMED_OR_MERGED"), True)["decision"] == "NO_DEEP_REVIEW"
    assert route_branch(row("agent/b", "SUPERSEDED_PRESERVE_ONLY"), True)["decision"] == "PRESERVE_ONLY"


def test_open_pr_is_deferred_even_if_release_relevant():
    result = route_branch(row("agent/a", "DIVERGED_REVIEW", open_prs=[75]), True)
    assert result["decision"] == "DEFER_TO_EXISTING_PR"


def test_unknown_release_relevance_is_preserved_not_suppressed():
    result = route_branch(row("agent/a", "DIVERGED_REVIEW"))
    assert result["decision"] == "NEEDS_RELEASE_RELEVANCE"
    assert result["release_relevance"] == "UNKNOWN"


def test_explicit_release_relevance_is_required_for_deep_review():
    candidate = row("agent/a", "AHEAD_AFTER_PRIOR_MERGE_REVIEW")
    assert route_branch(candidate, False)["decision"] == "DEFER_NON_RELEASE"
    assert route_branch(candidate, True)["decision"] == "DEEP_REVIEW_ELIGIBLE"


def test_snapshot_reports_reduction_without_mutation_authority():
    data = snapshot(
        row("agent/subsumed", "SUBSUMED_OR_MERGED"),
        row("agent/unknown", "DIVERGED_REVIEW"),
        row("agent/release", "CLOSED_UNMERGED_REVIEW"),
        row("agent/nonrelease", "AHEAD_AFTER_PRIOR_MERGE_REVIEW"),
    )
    result = route_snapshot(data, {"agent/release": "RELEVANT", "agent/nonrelease": "NOT_RELEVANT"})
    assert result["baseline_attention_count"] == 3
    assert result["deep_review_eligible_count"] == 1
    assert result["deep_review_reduction_count"] == 2
    assert result["policy"]["repository_mutation"] is False
    assert result["decision_counts"]["NEEDS_RELEASE_RELEVANCE"] == 1


def test_unknown_qualification_state_is_never_silently_dropped():
    result = route_branch(row("agent/a", "NEW_STATE"), True)
    assert result["decision"] == "AMBIGUOUS_REVIEW"


def test_frozen_issue75_snapshot_reduces_deep_review_until_release_relevance_is_explicit():
    import json

    fixture = Path(__file__).with_name("fixtures") / "agent_fleet_issue75_20260815.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    result = route_snapshot(data)
    assert data["agent_branch_count"] == 70
    assert result["branch_count"] == 70
    assert result["routed_branch_count"] == 52
    assert result["baseline_attention_count"] == 52
    assert result["deep_review_eligible_count"] == 0
    assert result["deep_review_reduction_count"] == 52
    assert result["decision_counts"] == {"NEEDS_RELEASE_RELEVANCE": 52}
