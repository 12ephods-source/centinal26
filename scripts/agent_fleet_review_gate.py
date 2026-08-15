"""Evidence-gated routing for Agent Fleet review candidates.

Consumes the machine-readable output of ``agent_fleet_qualify.py`` and produces a
proposal-only routing decision. It never mutates branches, PRs, issues, or main.
Deep-review eligibility requires immutable candidate identity plus an externally
supplied current-base SHA; stale or incomplete identity fails closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

NO_DEEP_REVIEW_STATES = {"SUBSUMED_OR_MERGED", "SUPERSEDED_PRESERVE_ONLY", "ACTIVE_PR"}
REVIEW_STATES = {
    "UNREVIEWED_AHEAD_CANDIDATE",
    "AHEAD_AFTER_PRIOR_MERGE_REVIEW",
    "CLOSED_UNMERGED_REVIEW",
    "DIVERGED_REVIEW",
}
SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def normalize_release_relevance(value: Any) -> str:
    if value is True or value == "RELEVANT":
        return "RELEVANT"
    if value is False or value == "NOT_RELEVANT":
        return "NOT_RELEVANT"
    return "UNKNOWN"


def normalize_sha(value: Any) -> str | None:
    text = str(value or "").strip()
    return text.lower() if SHA40_RE.fullmatch(text) else None


def route_branch(
    row: dict[str, Any],
    release_relevance: Any = None,
    *,
    source_base_sha: Any = None,
    expected_base_sha: Any = None,
    identity_conflict: bool = False,
) -> dict[str, Any]:
    state = str(row.get("state", ""))
    branch = str(row.get("branch", ""))
    relevance = normalize_release_relevance(release_relevance)
    open_prs = list(row.get("open_prs") or [])
    head_sha = normalize_sha(row.get("head_sha"))
    source_base = normalize_sha(source_base_sha)
    expected_base = normalize_sha(expected_base_sha)

    if state == "SUBSUMED_OR_MERGED":
        decision, reason = "NO_DEEP_REVIEW", "current base already subsumes branch changes"
    elif state == "SUPERSEDED_PRESERVE_ONLY":
        decision, reason = "PRESERVE_ONLY", "explicit supersession evidence blocks reuse"
    elif state == "ACTIVE_PR" or open_prs:
        decision, reason = "DEFER_TO_EXISTING_PR", "open PR/review path already exists"
    elif state not in REVIEW_STATES:
        decision, reason = "AMBIGUOUS_REVIEW", "unrecognized qualification state is preserved for review"
    elif identity_conflict:
        decision, reason = "AMBIGUOUS_IDENTITY", "branch appears with conflicting immutable head identities"
    elif head_sha is None:
        decision, reason = "NEEDS_IDENTITY_REFRESH", "candidate head_sha is missing or malformed"
    elif source_base is None or expected_base is None:
        decision, reason = "NEEDS_BASE_REFRESH", "qualification/current-base SHA binding is missing or malformed"
    elif source_base != expected_base:
        decision, reason = "NEEDS_BASE_REFRESH", "qualification snapshot base_sha is stale relative to expected current base"
    elif relevance == "UNKNOWN":
        decision, reason = "NEEDS_RELEASE_RELEVANCE", "release relevance lacks explicit evidence"
    elif relevance == "NOT_RELEVANT":
        decision, reason = "DEFER_NON_RELEASE", "explicit evidence marks candidate outside release-critical lane"
    else:
        decision, reason = "DEEP_REVIEW_ELIGIBLE", "immutable head/current-base/review/supersession/release-relevance gates passed"

    return {
        "branch": branch,
        "head_sha": head_sha,
        "source_base_sha": source_base,
        "expected_base_sha": expected_base,
        "qualification_state": state,
        "release_relevance": relevance,
        "decision": decision,
        "reason": reason,
        "mutates_repository": False,
    }


def route_snapshot(
    snapshot: dict[str, Any],
    release_relevance: dict[str, Any] | None = None,
    *,
    expected_base_sha: Any = None,
) -> dict[str, Any]:
    release_relevance = release_relevance or {}
    source_base_sha = snapshot.get("base_sha")
    heads_by_branch: dict[str, set[str]] = defaultdict(set)
    for row in snapshot.get("branches", []):
        branch = str(row.get("branch", ""))
        head = normalize_sha(row.get("head_sha"))
        if head:
            heads_by_branch[branch].add(head)

    rows = [
        route_branch(
            row,
            release_relevance.get(str(row.get("branch", ""))),
            source_base_sha=source_base_sha,
            expected_base_sha=expected_base_sha,
            identity_conflict=len(heads_by_branch[str(row.get("branch", ""))]) > 1,
        )
        for row in snapshot.get("branches", [])
    ]
    counts = Counter(row["decision"] for row in rows)
    baseline_attention = sum(
        1 for row in snapshot.get("branches", []) if row.get("state") not in NO_DEEP_REVIEW_STATES
    )
    deep_review = counts.get("DEEP_REVIEW_ELIGIBLE", 0)
    return {
        "schema": "frost-agent-fleet-review-gate/1.1",
        "source_schema": snapshot.get("schema"),
        "source_hash": canonical_hash(snapshot),
        "release_relevance_hash": canonical_hash(release_relevance),
        "repository": snapshot.get("repository"),
        "base": snapshot.get("base"),
        "source_base_sha": normalize_sha(source_base_sha),
        "expected_base_sha": normalize_sha(expected_base_sha),
        "branch_count": int(snapshot.get("agent_branch_count", len(rows))),
        "routed_branch_count": len(rows),
        "baseline_attention_count": baseline_attention,
        "deep_review_eligible_count": deep_review,
        "deep_review_reduction_count": baseline_attention - deep_review,
        "decision_counts": dict(sorted(counts.items())),
        "policy": {
            "proposal_only": True,
            "auto_merge": False,
            "repository_mutation": False,
            "unknown_release_relevance_is_preserved": True,
            "immutable_head_required": True,
            "current_base_sha_required": True,
            "conflicting_head_identity_fails_closed": True,
        },
        "branches": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="agent_fleet.json from agent_fleet_qualify.py")
    parser.add_argument("--release-relevance", type=Path, help="JSON object mapping branch name to RELEVANT/NOT_RELEVANT")
    parser.add_argument(
        "--expected-base-sha",
        required=True,
        help="40-hex current base commit SHA obtained independently from the qualification snapshot",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    snapshot = json.loads(args.input.read_text(encoding="utf-8"))
    relevance = json.loads(args.release_relevance.read_text(encoding="utf-8")) if args.release_relevance else {}
    result = route_snapshot(snapshot, relevance, expected_base_sha=args.expected_base_sha)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
