from __future__ import annotations

import argparse
import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

EXTERNAL_MARKERS = (
    "physical-device",
    "physical device",
    "android/termux",
    "device_validated",
    "provider execution boundary",
    "privileged base44",
    "dedicated repository",
    "repository creation",
    "external evidence",
    "classroom learning",
    "real retention observations",
)

MERGE_BLOCKING_MARKERS = (
    "should remain draft",
    "remain draft",
    "keep this pr draft",
    "must be demonstrated before",
    "should not be merged",
    "do not merge",
)


@dataclass(frozen=True)
class PRDecision:
    number: int
    title: str
    draft: bool
    mergeable: bool | None
    external_blocker: bool
    explicit_merge_blocker: bool
    actionable: bool
    reason: str


def classify_pr(pr: dict[str, Any]) -> PRDecision:
    body = (pr.get("body") or "").lower()
    title = pr.get("title") or ""
    draft = bool(pr.get("draft", False))
    mergeable = pr.get("mergeable")
    external = any(marker in body for marker in EXTERNAL_MARKERS)
    explicit = any(marker in body for marker in MERGE_BLOCKING_MARKERS)

    if explicit:
        actionable = False
        reason = "explicit_merge_boundary"
    elif draft and external:
        actionable = False
        reason = "external_dependency"
    elif draft:
        actionable = True
        reason = "draft_internal_work"
    elif mergeable is False:
        actionable = True
        reason = "repair_mergeability"
    else:
        actionable = True
        reason = "merge_eligible_or_qualify"

    return PRDecision(
        number=int(pr["number"]),
        title=title,
        draft=draft,
        mergeable=mergeable,
        external_blocker=external,
        explicit_merge_blocker=explicit,
        actionable=actionable,
        reason=reason,
    )


def rank(decisions: list[PRDecision]) -> list[PRDecision]:
    priority = {
        "repair_mergeability": 0,
        "merge_eligible_or_qualify": 1,
        "draft_internal_work": 2,
        "external_dependency": 8,
        "explicit_merge_boundary": 9,
    }
    return sorted(decisions, key=lambda d: (priority[d.reason], -d.number))


def reconcile(prs: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = rank([classify_pr(pr) for pr in prs])
    actionable = [d for d in decisions if d.actionable]
    blocked = [d for d in decisions if not d.actionable]
    return {
        "schema_version": 1,
        "actionable_count": len(actionable),
        "blocked_count": len(blocked),
        "next_action": asdict(actionable[0]) if actionable else None,
        "actionable": [asdict(d) for d in actionable],
        "blocked": [asdict(d) for d in blocked],
    }


def fetch_open_prs(repo: str, token: str | None) -> list[dict[str, Any]]:
    owner, name = repo.split("/", 1)
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{name}/pulls?state=open&per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "centinal26-project-goal-reconciler",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.load(response)
    return [
        {
            "number": item["number"],
            "title": item.get("title", ""),
            "body": item.get("body") or "",
            "draft": item.get("draft", False),
            "mergeable": None,
        }
        for item in data
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="12ephods-source/centinal26")
    parser.add_argument("--fixture")
    args = parser.parse_args()

    if args.fixture:
        with open(args.fixture, encoding="utf-8") as fh:
            prs = json.load(fh)
    else:
        prs = fetch_open_prs(args.repo, os.getenv("GITHUB_TOKEN"))
    print(json.dumps(reconcile(prs), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
