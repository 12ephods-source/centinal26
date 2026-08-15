import runpy
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "agent_fleet_qualify.py"
MODULE = runpy.run_path(MODULE_PATH)
classify = MODULE["classify"]


def cmp(ahead=0, behind=0):
    return {"ahead_by": ahead, "behind_by": behind}


def pr(number, state="closed", merged_at=None, title="", body=""):
    return {
        "number": number,
        "state": state,
        "merged_at": merged_at,
        "title": title,
        "body": body,
    }


def test_open_pr_takes_precedence():
    assert classify(cmp(ahead=2, behind=3), [pr(1, state="open")]) == "ACTIVE_PR"


def test_subsumed_branch_needs_no_action():
    assert classify(cmp(ahead=0, behind=8), []) == "SUBSUMED_OR_MERGED"


def test_post_merge_new_commits_require_review():
    assert classify(cmp(ahead=2), [pr(2, merged_at="2026-08-15T00:00:00Z")]) == "AHEAD_AFTER_PRIOR_MERGE_REVIEW"


def test_explicit_supersession_is_preserved_not_merged():
    old = pr(3, body="Superseded by PR #4. Preserve for provenance; do not merge.")
    assert classify(cmp(ahead=1, behind=4), [old]) == "SUPERSEDED_PRESERVE_ONLY"


def test_closed_unmerged_without_supersession_requires_review():
    assert classify(cmp(ahead=1, behind=2), [pr(4)]) == "CLOSED_UNMERGED_REVIEW"


def test_fresh_unreviewed_ahead_branch_is_candidate():
    assert classify(cmp(ahead=3, behind=0), []) == "UNREVIEWED_AHEAD_CANDIDATE"


def test_diverged_unreviewed_branch_requires_review():
    assert classify(cmp(ahead=3, behind=5), []) == "DIVERGED_REVIEW"
