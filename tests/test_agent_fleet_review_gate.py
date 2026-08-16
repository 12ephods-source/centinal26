import runpy
import sys
from pathlib import Path

import pytest

MODULE = runpy.run_path(Path(__file__).resolve().parents[1] / "scripts" / "agent_fleet_review_gate.py")
CANONICAL_REPOSITORY = MODULE["CANONICAL_REPOSITORY"]
CANONICAL_BASE = MODULE["CANONICAL_BASE"]
collect_live_state = MODULE["collect_live_state"]
route_snapshot = MODULE["route_snapshot"]
revalidate_observation = MODULE["revalidate_observation"]
main = MODULE["main"]

BASE = "b" * 40
HEAD = "a" * 40
NEW_HEAD = "c" * 40


def row(*, head=HEAD, state="AHEAD_AFTER_PRIOR_MERGE_REVIEW", open_prs=None):
    return {
        "branch": "agent/example",
        "head_sha": head,
        "state": state,
        "open_prs": open_prs or [],
    }


def snapshot(candidate=None, *, base_sha=BASE, repository=CANONICAL_REPOSITORY, base=CANONICAL_BASE):
    return {
        "schema": "frost-agent-fleet-qualification/1.1",
        "repository": repository,
        "base": base,
        "base_sha": base_sha,
        "branches": [candidate or row()],
    }


def observation(*, main=BASE, head=HEAD, prs=None, repository=CANONICAL_REPOSITORY, base=CANONICAL_BASE):
    return {
        "schema": "frost-agent-fleet-live-observation/1.1",
        "repository": repository,
        "base": base,
        "current_main_sha": main,
        "branches": {
            "agent/example": {
                "live_head_sha": head,
                "open_prs": prs or [],
            }
        },
    }


def live_pr(*, number=78, head=HEAD, base=BASE, requested=None, reviews=None, draft=True):
    return {
        "number": number,
        "head_sha": head,
        "base_sha": base,
        "state": "open",
        "draft": draft,
        "merged": False,
        "requested_reviewers": requested or [],
        "latest_reviews": reviews or [],
    }


def decision(candidate=None, *, live=None, relevance="RELEVANT", base_sha=BASE, repository=CANONICAL_REPOSITORY, base=CANONICAL_BASE):
    result = route_snapshot(
        snapshot(candidate, base_sha=base_sha, repository=repository, base=base),
        live or observation(),
        {"agent/example": relevance},
    )
    return result["branches"][0]


def test_release_relevant_candidate_requires_live_identity_and_current_main():
    result = decision()
    assert result["decision"] == "DEEP_REVIEW_ELIGIBLE"
    assert result["live_head_sha"] == HEAD
    assert result["current_main_sha"] == BASE


def test_stale_main_fails_closed():
    result = decision(live=observation(main="d" * 40))
    assert result["decision"] == "NEEDS_BASE_REFRESH"


def test_changed_head_with_unchanged_main_fails_closed():
    result = decision(live=observation(head=NEW_HEAD))
    assert result["decision"] == "NEEDS_IDENTITY_REFRESH"


def test_new_open_pr_after_qualification_fails_closed():
    result = decision(live=observation(prs=[live_pr()]))
    assert result["decision"] == "NEEDS_REVIEW_REFRESH"


def test_existing_pr_binds_live_head_base_and_review_state():
    candidate = row(open_prs=[78], state="ACTIVE_PR")
    pr = live_pr(
        requested=["alice"],
        reviews=[{"reviewer": "bob", "state": "APPROVED"}],
    )
    result = decision(candidate, live=observation(prs=[pr]))
    assert result["decision"] == "DEFER_TO_EXISTING_PR"
    assert result["live_open_prs"] == [78]
    assert result["live_review_state_hash"]


def test_stale_pr_base_fails_closed_even_when_main_unchanged():
    candidate = row(open_prs=[78], state="ACTIVE_PR")
    result = decision(candidate, live=observation(prs=[live_pr(base="d" * 40)]))
    assert result["decision"] == "NEEDS_BASE_REFRESH"


def test_missing_pr_after_qualification_fails_closed():
    candidate = row(open_prs=[78], state="ACTIVE_PR")
    result = decision(candidate, live=observation(prs=[]))
    assert result["decision"] == "NEEDS_REVIEW_REFRESH"


def test_conflicting_duplicate_qualification_heads_fail_closed():
    data = snapshot()
    data["branches"].append({**row(head=NEW_HEAD)})
    result = route_snapshot(data, observation(), {"agent/example": "RELEVANT"})
    assert result["decision_counts"] == {"AMBIGUOUS_IDENTITY": 2}


def test_review_state_change_is_detected_by_revalidation():
    before = observation(prs=[live_pr(requested=["alice"])])
    after = observation(prs=[live_pr(requested=["bob"])])
    result = revalidate_observation(before, after)
    assert result["match"] is False
    assert result["mismatches"] == ["agent/example:review_state"]


def test_head_change_is_detected_by_revalidation():
    result = revalidate_observation(observation(), observation(head=NEW_HEAD))
    assert result["match"] is False
    assert result["mismatches"] == ["agent/example:head"]


def test_main_change_is_detected_by_revalidation():
    result = revalidate_observation(observation(), observation(main="d" * 40))
    assert result["match"] is False
    assert result["mismatches"] == ["current_main_sha"]


def test_proposal_only_policy_is_explicit():
    result = route_snapshot(snapshot(), observation(), {"agent/example": "RELEVANT"})
    assert result["policy"]["proposal_only"] is True
    assert result["policy"]["repository_mutation"] is False
    assert result["policy"]["auto_merge"] is False
    assert result["policy"]["canonical_repository"] == CANONICAL_REPOSITORY
    assert result["policy"]["canonical_base"] == CANONICAL_BASE
    assert result["policy"]["canonical_identity_snapshot_override"] is False
    assert result["policy"]["exact_observation_revalidation_required_before_consequential_action"] is True


def test_noncanonical_snapshot_repository_fails_closed_even_with_matching_shas():
    result = decision(repository="attacker/example")
    assert result["decision"] == "INVALID_CANONICAL_IDENTITY"


def test_non_main_snapshot_base_fails_closed_even_with_matching_shas():
    result = decision(base="agent/fake-main")
    assert result["decision"] == "INVALID_CANONICAL_IDENTITY"


def test_noncanonical_live_observation_identity_fails_closed():
    result = decision(live=observation(repository="attacker/example"))
    assert result["decision"] == "INVALID_CANONICAL_IDENTITY"


def test_collect_live_state_rejects_wrong_repository_before_any_request():
    calls = []

    def request(path):
        calls.append(path)
        raise AssertionError("request must not execute for invalid canonical identity")

    with pytest.raises(ValueError, match="qualification repository"):
        collect_live_state(snapshot(repository="attacker/example"), request_fn=request)
    assert calls == []


def test_collect_live_state_rejects_wrong_base_before_any_request():
    calls = []

    def request(path):
        calls.append(path)
        raise AssertionError("request must not execute for invalid canonical identity")

    with pytest.raises(ValueError, match="qualification base"):
        collect_live_state(snapshot(base="agent/fake-main"), request_fn=request)
    assert calls == []


def test_collect_live_state_queries_configured_main_not_snapshot_selected_ref():
    calls = []
    data = snapshot()
    data["branches"] = []

    def request(path):
        calls.append(path)
        return {"object": {"sha": BASE}}

    live = collect_live_state(data, request_fn=request)
    assert calls == [f"/repos/{CANONICAL_REPOSITORY}/git/ref/heads/main"]
    assert live["repository"] == CANONICAL_REPOSITORY
    assert live["base"] == CANONICAL_BASE
    assert live["current_main_sha"] == BASE


def test_revalidation_rejects_noncanonical_identity():
    result = revalidate_observation(observation(), observation(base="agent/fake-main"))
    assert result["match"] is False
    assert result["mismatches"] == ["base"]


def test_production_cli_rejects_precollected_live_observation(monkeypatch, tmp_path):
    input_path = tmp_path / "agent_fleet.json"
    input_path.write_text("{}", encoding="utf-8")
    live_path = tmp_path / "fabricated-live.json"
    live_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agent_fleet_review_gate.py",
            str(input_path),
            "--live-observation",
            str(live_path),
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


def test_production_cli_rejects_noncanonical_snapshot_without_network(monkeypatch, tmp_path, capsys):
    input_path = tmp_path / "agent_fleet.json"
    input_path.write_text(
        '{"repository":"attacker/example","base":"main","base_sha":"' + BASE + '","branches":[]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["agent_fleet_review_gate.py", str(input_path)])
    assert main() == 2
    assert "qualification repository" in capsys.readouterr().err
