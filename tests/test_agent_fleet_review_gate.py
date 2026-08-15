import runpy
from pathlib import Path

MODULE = runpy.run_path(Path(__file__).resolve().parents[1] / "scripts" / "agent_fleet_review_gate.py")
route_branch = MODULE["route_branch"]
route_snapshot = MODULE["route_snapshot"]

BASE = "b" * 40
OTHER_BASE = "c" * 40


def row(branch, state, *, open_prs=None, head_sha=None):
    return {
        "branch": branch,
        "head_sha": head_sha if head_sha is not None else "a" * 40,
        "state": state,
        "open_prs": open_prs or [],
    }


def snapshot(*rows, base_sha=BASE):
    return {
        "schema": "frost-agent-fleet-qualification/1.0",
        "repository": "12ephods-source/centinal26",
        "base": "main",
        "base_sha": base_sha,
        "branches": list(rows),
    }


def routed(candidate, relevance=None, *, source_base_sha=BASE, expected_base_sha=BASE, identity_conflict=False):
    return route_branch(
        candidate,
        relevance,
        source_base_sha=source_base_sha,
        expected_base_sha=expected_base_sha,
        identity_conflict=identity_conflict,
    )


def test_subsumed_and_superseded_never_enter_deep_review():
    assert routed(row("agent/a", "SUBSUMED_OR_MERGED"), True)["decision"] == "NO_DEEP_REVIEW"
    assert routed(row("agent/b", "SUPERSEDED_PRESERVE_ONLY"), True)["decision"] == "PRESERVE_ONLY"


def test_open_pr_is_deferred_even_if_release_relevant():
    result = routed(row("agent/a", "DIVERGED_REVIEW", open_prs=[75]), True)
    assert result["decision"] == "DEFER_TO_EXISTING_PR"


def test_unknown_release_relevance_is_preserved_not_suppressed():
    result = routed(row("agent/a", "DIVERGED_REVIEW"))
    assert result["decision"] == "NEEDS_RELEASE_RELEVANCE"
    assert result["release_relevance"] == "UNKNOWN"


def test_explicit_release_relevance_is_required_for_deep_review():
    candidate = row("agent/a", "AHEAD_AFTER_PRIOR_MERGE_REVIEW")
    assert routed(candidate, False)["decision"] == "DEFER_NON_RELEASE"
    assert routed(candidate, True)["decision"] == "DEEP_REVIEW_ELIGIBLE"


def test_missing_head_identity_fails_closed_before_release_relevance():
    candidate = row("agent/a", "AHEAD_AFTER_PRIOR_MERGE_REVIEW", head_sha="")
    result = routed(candidate, True)
    assert result["decision"] == "NEEDS_IDENTITY_REFRESH"
    assert result["head_sha"] is None


def test_missing_or_stale_base_binding_fails_closed():
    candidate = row("agent/a", "AHEAD_AFTER_PRIOR_MERGE_REVIEW")
    assert routed(candidate, True, source_base_sha=None)["decision"] == "NEEDS_BASE_REFRESH"
    assert routed(candidate, True, source_base_sha=OTHER_BASE)["decision"] == "NEEDS_BASE_REFRESH"


def test_snapshot_requires_independently_supplied_current_base_sha():
    data = snapshot(row("agent/release", "AHEAD_AFTER_PRIOR_MERGE_REVIEW"))
    assert route_snapshot(data, {"agent/release": "RELEVANT"})["branches"][0]["decision"] == "NEEDS_BASE_REFRESH"
    assert (
        route_snapshot(data, {"agent/release": "RELEVANT"}, expected_base_sha=BASE)["branches"][0]["decision"]
        == "DEEP_REVIEW_ELIGIBLE"
    )


def test_conflicting_duplicate_branch_heads_fail_closed():
    data = snapshot(
        row("agent/conflict", "AHEAD_AFTER_PRIOR_MERGE_REVIEW", head_sha="1" * 40),
        row("agent/conflict", "AHEAD_AFTER_PRIOR_MERGE_REVIEW", head_sha="2" * 40),
    )
    result = route_snapshot(data, {"agent/conflict": "RELEVANT"}, expected_base_sha=BASE)
    assert result["deep_review_eligible_count"] == 0
    assert result["decision_counts"] == {"AMBIGUOUS_IDENTITY": 2}


def test_snapshot_reports_reduction_without_mutation_authority():
    data = snapshot(
        row("agent/subsumed", "SUBSUMED_OR_MERGED"),
        row("agent/unknown", "DIVERGED_REVIEW"),
        row("agent/release", "CLOSED_UNMERGED_REVIEW"),
        row("agent/nonrelease", "AHEAD_AFTER_PRIOR_MERGE_REVIEW"),
    )
    result = route_snapshot(
        data,
        {"agent/release": "RELEVANT", "agent/nonrelease": "NOT_RELEVANT"},
        expected_base_sha=BASE,
    )
    assert result["baseline_attention_count"] == 3
    assert result["deep_review_eligible_count"] == 1
    assert result["deep_review_reduction_count"] == 2
    assert result["policy"]["repository_mutation"] is False
    assert result["policy"]["immutable_head_required"] is True
    assert result["policy"]["current_base_sha_required"] is True
    assert result["decision_counts"]["NEEDS_RELEASE_RELEVANCE"] == 1


def test_unknown_qualification_state_is_never_silently_dropped():
    result = routed(row("agent/a", "NEW_STATE"), True)
    assert result["decision"] == "AMBIGUOUS_REVIEW"


def test_frozen_issue75_snapshot_fails_closed_until_identity_is_refreshed():
    import json

    fixture = Path(__file__).with_name("fixtures") / "agent_fleet_issue75_20260815.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    result = route_snapshot(data, expected_base_sha=BASE)
    assert data["agent_branch_count"] == 70
    assert result["branch_count"] == 70
    assert result["routed_branch_count"] == 52
    assert result["baseline_attention_count"] == 52
    assert result["deep_review_eligible_count"] == 0
    assert result["deep_review_reduction_count"] == 52
    assert result["decision_counts"] == {"NEEDS_IDENTITY_REFRESH": 52}
