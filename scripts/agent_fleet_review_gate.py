"""Live, fail-closed routing for Agent Fleet review candidates.

Consumes fresh ``agent_fleet_qualify.py`` JSON and independently refreshes the
configured canonical repository/main plus live branch/PR/review state. Output is
proposal evidence only; this module never mutates GitHub state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

API = "https://api.github.com"
CANONICAL_REPOSITORY = "12ephods-source/centinal26"
CANONICAL_BASE = "main"
CANONICAL_BASE_REF_PATH = "heads/main"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
NO_DEEP_REVIEW_STATES = {"SUBSUMED_OR_MERGED", "SUPERSEDED_PRESERVE_ONLY"}
REVIEW_STATES = {
    "UNREVIEWED_AHEAD_CANDIDATE",
    "AHEAD_AFTER_PRIOR_MERGE_REVIEW",
    "CLOSED_UNMERGED_REVIEW",
    "DIVERGED_REVIEW",
}
RequestFn = Callable[[str], Any]


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def normalize_sha(value: Any) -> str | None:
    text = str(value or "").strip()
    return text.lower() if SHA40_RE.fullmatch(text) else None


def normalize_release_relevance(value: Any) -> str:
    if value is True or value == "RELEVANT":
        return "RELEVANT"
    if value is False or value == "NOT_RELEVANT":
        return "NOT_RELEVANT"
    return "UNKNOWN"


def canonical_identity_error(snapshot: dict[str, Any]) -> str | None:
    repository = str(snapshot.get("repository") or "")
    base = str(snapshot.get("base") or "")
    if repository != CANONICAL_REPOSITORY:
        return f"qualification repository must be {CANONICAL_REPOSITORY}"
    if base != CANONICAL_BASE:
        return f"qualification base must be {CANONICAL_BASE}"
    return None


def github_request(path: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "centinal26-agent-fleet-review-gate/3.0",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(API + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub API {exc.code} for {path}: {body[:1000]}") from exc


def _latest_review_states(reviews: list[dict[str, Any]]) -> list[dict[str, str]]:
    latest: dict[str, tuple[str, str]] = {}
    for review in reviews:
        user = str((review.get("user") or {}).get("login") or "")
        state = str(review.get("state") or "")
        submitted = str(review.get("submitted_at") or "")
        if not user or not state:
            continue
        previous = latest.get(user)
        if previous is None or submitted >= previous[0]:
            latest[user] = (submitted, state)
    return [
        {"reviewer": reviewer, "state": state}
        for reviewer, (_submitted, state) in sorted(latest.items())
    ]


def _normalize_pr(pr: dict[str, Any], reviews: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "number": int(pr.get("number", 0)),
        "head_sha": normalize_sha((pr.get("head") or {}).get("sha")),
        "base_sha": normalize_sha((pr.get("base") or {}).get("sha")),
        "state": str(pr.get("state") or ""),
        "draft": bool(pr.get("draft", False)),
        "merged": bool(pr.get("merged_at")),
        "requested_reviewers": sorted(
            str(item.get("login"))
            for item in (pr.get("requested_reviewers") or [])
            if item.get("login")
        ),
        "latest_reviews": _latest_review_states(reviews),
    }


def collect_live_state(
    snapshot: dict[str, Any],
    *,
    request_fn: RequestFn = github_request,
) -> dict[str, Any]:
    error = canonical_identity_error(snapshot)
    if error:
        raise ValueError(error)

    repository = CANONICAL_REPOSITORY
    owner = repository.split("/", 1)[0]
    main_ref = request_fn(f"/repos/{repository}/git/ref/{CANONICAL_BASE_REF_PATH}")
    current_main_sha = normalize_sha((main_ref.get("object") or {}).get("sha"))

    branches: dict[str, Any] = {}
    branch_names = {
        str(row.get("branch") or "")
        for row in snapshot.get("branches", [])
        if row.get("branch")
    }
    for branch in sorted(branch_names):
        branch_ref = urllib.parse.quote(branch, safe="")
        ref = request_fn(f"/repos/{repository}/git/ref/heads/{branch_ref}")
        live_head_sha = normalize_sha((ref.get("object") or {}).get("sha"))

        encoded_head = urllib.parse.quote(f"{owner}:{branch}", safe=":")
        prs = request_fn(f"/repos/{repository}/pulls?state=open&head={encoded_head}&per_page=100")
        normalized_prs = []
        for pr in sorted(prs, key=lambda item: int(item.get("number", 0))):
            number = int(pr.get("number", 0))
            reviews = request_fn(f"/repos/{repository}/pulls/{number}/reviews?per_page=100")
            normalized_prs.append(_normalize_pr(pr, reviews))

        branches[branch] = {
            "live_head_sha": live_head_sha,
            "open_prs": normalized_prs,
        }

    observation = {
        "schema": "frost-agent-fleet-live-observation/1.1",
        "repository": CANONICAL_REPOSITORY,
        "base": CANONICAL_BASE,
        "current_main_sha": current_main_sha,
        "branches": branches,
    }
    observation["observation_hash"] = canonical_hash(observation)
    return observation


def _identity_conflicts(snapshot: dict[str, Any]) -> set[str]:
    heads_by_branch: dict[str, set[str]] = defaultdict(set)
    for row in snapshot.get("branches", []):
        branch = str(row.get("branch") or "")
        head = normalize_sha(row.get("head_sha"))
        if branch and head:
            heads_by_branch[branch].add(head)
    return {branch for branch, heads in heads_by_branch.items() if len(heads) > 1}


def _review_state_digest(prs: list[dict[str, Any]]) -> str:
    return canonical_hash(prs)


def route_branch(
    row: dict[str, Any],
    live: dict[str, Any] | None,
    release_relevance: Any,
    *,
    snapshot_base_sha: Any,
    current_main_sha: Any,
    identity_conflict: bool = False,
    canonical_identity_valid: bool = True,
) -> dict[str, Any]:
    branch = str(row.get("branch") or "")
    state = str(row.get("state") or "")
    relevance = normalize_release_relevance(release_relevance)
    snapshot_head = normalize_sha(row.get("head_sha"))
    snapshot_base = normalize_sha(snapshot_base_sha)
    current_main = normalize_sha(current_main_sha)
    live = live or {}
    live_head = normalize_sha(live.get("live_head_sha"))
    live_prs = list(live.get("open_prs") or [])
    snapshot_open_prs = sorted(int(value) for value in (row.get("open_prs") or []))
    live_open_prs = sorted(int(pr.get("number", 0)) for pr in live_prs)

    decision = "AMBIGUOUS_REVIEW"
    reason = "unrecognized qualification state is preserved for review"

    if not canonical_identity_valid:
        decision, reason = "INVALID_CANONICAL_IDENTITY", "qualification/live identity does not match configured canonical repository/main"
    elif state == "SUBSUMED_OR_MERGED":
        decision, reason = "NO_DEEP_REVIEW", "fresh qualification says current base subsumes branch changes"
    elif state == "SUPERSEDED_PRESERVE_ONLY":
        decision, reason = "PRESERVE_ONLY", "explicit supersession evidence blocks reuse"
    elif identity_conflict:
        decision, reason = "AMBIGUOUS_IDENTITY", "qualification contains conflicting immutable branch heads"
    elif current_main is None or snapshot_base is None:
        decision, reason = "NEEDS_BASE_REFRESH", "current or qualification base SHA is missing or malformed"
    elif snapshot_base != current_main:
        decision, reason = "NEEDS_BASE_REFRESH", "qualification base SHA is stale relative to independently refreshed main"
    elif snapshot_head is None or live_head is None:
        decision, reason = "NEEDS_IDENTITY_REFRESH", "qualification or live branch head is missing or malformed"
    elif snapshot_head != live_head:
        decision, reason = "NEEDS_IDENTITY_REFRESH", "branch head changed after qualification"
    elif len(live_prs) > 1:
        decision, reason = "AMBIGUOUS_REVIEW", "multiple live open PRs exist for one candidate branch"
    elif snapshot_open_prs != live_open_prs:
        decision, reason = "NEEDS_REVIEW_REFRESH", "open-PR state changed after qualification"
    elif live_prs:
        pr = live_prs[0]
        if normalize_sha(pr.get("head_sha")) != live_head:
            decision, reason = "AMBIGUOUS_IDENTITY", "live PR head disagrees with live branch head"
        elif normalize_sha(pr.get("base_sha")) != current_main:
            decision, reason = "NEEDS_BASE_REFRESH", "live PR base is stale relative to independently refreshed main"
        elif pr.get("state") != "open" or pr.get("merged"):
            decision, reason = "NEEDS_REVIEW_REFRESH", "live PR state changed during observation"
        else:
            decision, reason = "DEFER_TO_EXISTING_PR", "live PR identity and review state are bound for existing review"
    elif state not in REVIEW_STATES:
        pass
    elif relevance == "UNKNOWN":
        decision, reason = "NEEDS_RELEASE_RELEVANCE", "release relevance lacks explicit structured evidence"
    elif relevance == "NOT_RELEVANT":
        decision, reason = "DEFER_NON_RELEASE", "explicit evidence marks candidate outside release-critical lane"
    else:
        decision, reason = (
            "DEEP_REVIEW_ELIGIBLE",
            "canonical live main/head/no-open-PR/supersession/release-relevance gates passed",
        )

    return {
        "branch": branch,
        "snapshot_head_sha": snapshot_head,
        "live_head_sha": live_head,
        "snapshot_base_sha": snapshot_base,
        "current_main_sha": current_main,
        "qualification_state": state,
        "snapshot_open_prs": snapshot_open_prs,
        "live_open_prs": live_open_prs,
        "live_review_state_hash": _review_state_digest(live_prs),
        "release_relevance": relevance,
        "decision": decision,
        "reason": reason,
        "mutates_repository": False,
    }


def route_snapshot(
    snapshot: dict[str, Any],
    live_observation: dict[str, Any],
    release_relevance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    release_relevance = release_relevance or {}
    conflicts = _identity_conflicts(snapshot)
    snapshot_identity_error = canonical_identity_error(snapshot)
    live_identity_valid = (
        str(live_observation.get("repository") or "") == CANONICAL_REPOSITORY
        and str(live_observation.get("base") or "") == CANONICAL_BASE
    )
    canonical_identity_valid = snapshot_identity_error is None and live_identity_valid

    rows = [
        route_branch(
            row,
            (live_observation.get("branches") or {}).get(str(row.get("branch") or "")),
            release_relevance.get(str(row.get("branch") or "")),
            snapshot_base_sha=snapshot.get("base_sha"),
            current_main_sha=live_observation.get("current_main_sha"),
            identity_conflict=str(row.get("branch") or "") in conflicts,
            canonical_identity_valid=canonical_identity_valid,
        )
        for row in snapshot.get("branches", [])
    ]
    counts = Counter(row["decision"] for row in rows)
    baseline_attention = sum(
        1 for row in snapshot.get("branches", []) if row.get("state") not in NO_DEEP_REVIEW_STATES
    )
    result = {
        "schema": "frost-agent-fleet-review-gate/3.0",
        "source_schema": snapshot.get("schema"),
        "source_hash": canonical_hash(snapshot),
        "live_observation_hash": live_observation.get("observation_hash") or canonical_hash(live_observation),
        "release_relevance_hash": canonical_hash(release_relevance),
        "repository": CANONICAL_REPOSITORY,
        "base": CANONICAL_BASE,
        "snapshot_repository": snapshot.get("repository"),
        "snapshot_base": snapshot.get("base"),
        "snapshot_base_sha": normalize_sha(snapshot.get("base_sha")),
        "current_main_sha": normalize_sha(live_observation.get("current_main_sha")),
        "canonical_identity_valid": canonical_identity_valid,
        "canonical_identity_error": snapshot_identity_error if snapshot_identity_error else (None if live_identity_valid else "live observation canonical identity mismatch"),
        "routed_branch_count": len(rows),
        "baseline_attention_count": baseline_attention,
        "deep_review_eligible_count": counts.get("DEEP_REVIEW_ELIGIBLE", 0),
        "decision_counts": dict(sorted(counts.items())),
        "policy": {
            "proposal_only": True,
            "repository_mutation": False,
            "auto_merge": False,
            "canonical_repository": CANONICAL_REPOSITORY,
            "canonical_base": CANONICAL_BASE,
            "canonical_identity_snapshot_override": False,
            "live_head_required": True,
            "live_main_required": True,
            "live_pr_review_state_bound": True,
            "exact_observation_revalidation_required_before_consequential_action": True,
        },
        "branches": rows,
    }
    result["routing_hash"] = canonical_hash(result)
    return result


def revalidate_observation(expected: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    mismatches: list[str] = []
    for field, expected_value in (("repository", CANONICAL_REPOSITORY), ("base", CANONICAL_BASE)):
        if expected.get(field) != expected_value or current.get(field) != expected_value:
            mismatches.append(field)
    if normalize_sha(expected.get("current_main_sha")) != normalize_sha(current.get("current_main_sha")):
        mismatches.append("current_main_sha")

    expected_branches = expected.get("branches") or {}
    current_branches = current.get("branches") or {}
    if set(expected_branches) != set(current_branches):
        mismatches.append("branch_set")

    for branch in sorted(set(expected_branches) & set(current_branches)):
        old = expected_branches[branch]
        new = current_branches[branch]
        if normalize_sha(old.get("live_head_sha")) != normalize_sha(new.get("live_head_sha")):
            mismatches.append(f"{branch}:head")
        if canonical_hash(old.get("open_prs") or []) != canonical_hash(new.get("open_prs") or []):
            mismatches.append(f"{branch}:review_state")

    return {
        "schema": "frost-agent-fleet-observation-revalidation/1.1",
        "match": not mismatches,
        "mismatches": mismatches,
        "expected_hash": expected.get("observation_hash") or canonical_hash(expected),
        "current_hash": current.get("observation_hash") or canonical_hash(current),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="fresh agent_fleet.json from agent_fleet_qualify.py")
    parser.add_argument("--release-relevance", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    snapshot = json.loads(args.input.read_text(encoding="utf-8"))
    relevance = json.loads(args.release_relevance.read_text(encoding="utf-8")) if args.release_relevance else {}
    error = canonical_identity_error(snapshot)
    if error:
        print(error, file=os.sys.stderr)
        return 2
    if not TOKEN:
        print("GITHUB_TOKEN is required for mandatory independent live refresh", file=os.sys.stderr)
        return 2
    try:
        live = collect_live_state(snapshot)
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=os.sys.stderr)
        return 2

    result = route_snapshot(snapshot, live, relevance)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
