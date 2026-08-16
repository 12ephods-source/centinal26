"""Qualify agent/* branches without executing or merging agent code."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "12ephods-source/centinal26")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
BASE = os.environ.get("FROST_AGENT_BASE", "main")
OUT = Path(os.environ.get("FROST_AGENT_FLEET_OUT", "artifacts/agent-fleet"))


def request(path: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "centinal26-agent-fleet-qualifier/1.0",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(API + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub API {exc.code} for {path}: {body[:1000]}") from exc


def paginate(path: str):
    items = []
    page = 1
    join = "&" if "?" in path else "?"
    while True:
        batch = request(f"{path}{join}per_page=100&page={page}")
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


def branch_prs(owner: str, branch: str):
    head = urllib.parse.quote(f"{owner}:{branch}", safe=":")
    return request(f"/repos/{REPO}/pulls?state=all&head={head}&per_page=100")


def compare(branch: str):
    base = urllib.parse.quote(BASE, safe="")
    head = urllib.parse.quote(branch, safe="")
    return request(f"/repos/{REPO}/compare/{base}...{head}")


def classify(cmp, prs):
    open_prs = [p for p in prs if p.get("state") == "open"]
    merged_prs = [p for p in prs if p.get("merged_at")]
    closed_unmerged = [p for p in prs if p.get("state") == "closed" and not p.get("merged_at")]
    ahead = int(cmp.get("ahead_by", 0))
    behind = int(cmp.get("behind_by", 0))

    if open_prs:
        return "ACTIVE_PR"
    if ahead == 0:
        return "SUBSUMED_OR_MERGED"
    if merged_prs:
        return "AHEAD_AFTER_PRIOR_MERGE_REVIEW"
    if closed_unmerged:
        text = "\n".join((p.get("title") or "") + "\n" + (p.get("body") or "") for p in closed_unmerged).lower()
        if "superseded" in text or "do not merge" in text:
            return "SUPERSEDED_PRESERVE_ONLY"
        return "CLOSED_UNMERGED_REVIEW"
    if behind == 0:
        return "UNREVIEWED_AHEAD_CANDIDATE"
    return "DIVERGED_REVIEW"


def main() -> int:
    if not TOKEN:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 2

    owner = REPO.split("/", 1)[0]
    branches = [b for b in paginate(f"/repos/{REPO}/branches") if b["name"].startswith("agent/")]
    rows = []

    for item in sorted(branches, key=lambda b: b["name"]):
        name = item["name"]
        cmp = compare(name)
        prs = branch_prs(owner, name)
        state = classify(cmp, prs)
        rows.append(
            {
                "branch": name,
                "head_sha": item["commit"]["sha"],
                "state": state,
                "compare_status": cmp.get("status"),
                "ahead_by": cmp.get("ahead_by", 0),
                "behind_by": cmp.get("behind_by", 0),
                "total_commits": cmp.get("total_commits", 0),
                "open_prs": [p["number"] for p in prs if p.get("state") == "open"],
                "merged_prs": [p["number"] for p in prs if p.get("merged_at")],
                "closed_unmerged_prs": [p["number"] for p in prs if p.get("state") == "closed" and not p.get("merged_at")],
            }
        )

    counts = Counter(r["state"] for r in rows)
    base_ref = request(f"/repos/{REPO}/git/ref/heads/{urllib.parse.quote(BASE, safe='')}")
    base_sha = (base_ref.get("object") or {}).get("sha")
    generated = datetime.now(UTC).isoformat()
    result = {
        "schema": "frost-agent-fleet-qualification/1.1",
        "generated_at": generated,
        "repository": REPO,
        "base": BASE,
        "base_sha": base_sha,
        "agent_branch_count": len(rows),
        "counts": dict(sorted(counts.items())),
        "policy": {
            "executes_agent_code": False,
            "auto_merges": False,
            "agent_self_authorization": False,
            "purpose": "Inventory and triage agent-produced branches for canonical review.",
        },
        "branches": rows,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "agent_fleet.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Agent Fleet Qualification Dashboard",
        "",
        f"Generated: `{generated}`",
        f"Repository: `{REPO}`",
        f"Canonical base: `{BASE}`",
        f"Canonical base SHA: `{base_sha}`",
        f"Agent branches inspected: **{len(rows)}**",
        "",
        "Agents are proposal sources only. This controller does not execute agent code, grant authorization, or auto-merge branches.",
        "",
        "## State counts",
        "",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"- `{key}`: **{value}**")

    attention = [r for r in rows if r["state"] not in {"SUBSUMED_OR_MERGED", "SUPERSEDED_PRESERVE_ONLY"}]
    lines.extend(["", "## Branches requiring attention", ""])
    if not attention:
        lines.append("No agent branch currently requires canonical review.")
    else:
        lines.append("| Branch | State | Ahead | Behind | PRs |")
        lines.append("|---|---:|---:|---:|---|")
        for r in attention:
            prs = sorted(set(r["open_prs"] + r["merged_prs"] + r["closed_unmerged_prs"]))
            pr_text = ", ".join(f"#{n}" for n in prs) if prs else "—"
            lines.append(f"| `{r['branch']}` | `{r['state']}` | {r['ahead_by']} | {r['behind_by']} | {pr_text} |")

    lines.extend([
        "",
        "## Automatic decision boundary",
        "",
        "- `SUBSUMED_OR_MERGED`: no action.",
        "- `SUPERSEDED_PRESERVE_ONLY`: retain for provenance; do not merge.",
        "- `ACTIVE_PR`: let repository CI/review arbitrate.",
        "- `UNREVIEWED_AHEAD_CANDIDATE`: candidate for a new bounded review PR.",
        "- `AHEAD_AFTER_PRIOR_MERGE_REVIEW`, `CLOSED_UNMERGED_REVIEW`, `DIVERGED_REVIEW`: inspect before reuse; never merge wholesale automatically.",
        "",
        "This dashboard is triage evidence, not a release or device-validation certificate.",
    ])
    (OUT / "agent_fleet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(result["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
