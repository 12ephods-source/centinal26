"""Fail-closed repository work-intake gate for Centinal26 critical-path mode."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TRAILER_RE = re.compile(
    r"^(Critical-Path-(?:Class|Blocker|Result|State)):\s*(.*?)\s*$", re.IGNORECASE
)


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_trailers(body: str) -> dict[str, str]:
    trailers: dict[str, str] = {}
    for line in body.splitlines():
        match = TRAILER_RE.match(line.strip())
        if match:
            trailers[match.group(1).lower()] = match.group(2).strip()
    return trailers


def active_blockers(
    policy: dict[str, Any], overrides: dict[str, str] | None = None
) -> dict[str, str]:
    overrides = overrides or {}
    active_states = set(policy["active_blocker_states"])
    result: dict[str, str] = {}
    for blocker in policy["blockers"]:
        blocker_id = blocker["id"]
        state = overrides.get(blocker_id, blocker["state"])
        if state in active_states:
            result[blocker_id] = state
    return result


def classify(
    policy: dict[str, Any],
    body: str,
    *,
    base_branch: str = "main",
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    blockers = active_blockers(policy, overrides)
    trailers = parse_trailers(body)

    verdict: dict[str, Any] = {
        "schema": "centinal26.critical_path_verdict/v1",
        "mode": policy["mode"],
        "base_branch": base_branch,
        "active_blockers": blockers,
        "trailers": trailers,
        "decision": "ALLOW",
        "reason": "critical_path_inactive",
    }

    if policy["mode"] != "CRITICAL_PATH" or not blockers:
        return verdict
    if base_branch != policy["enforced_base_branch"]:
        verdict["reason"] = "base_not_governed"
        return verdict

    state = trailers.get("critical-path-state", "").upper()
    if state == "DEFERRED":
        verdict.update(decision="DEFER", reason="explicitly_deferred")
        return verdict

    work_class = trailers.get("critical-path-class", "")
    blocker_id = trailers.get("critical-path-blocker", "")
    result = trailers.get("critical-path-result", "")

    if not work_class:
        verdict.update(decision="DEFER", reason="missing_critical_path_class")
        return verdict
    if work_class not in policy["allowed_work_classes"]:
        verdict.update(decision="DEFER", reason="work_class_not_allowed")
        return verdict
    if blocker_id not in blockers:
        verdict.update(decision="DEFER", reason="blocker_not_active")
        return verdict
    if not result:
        verdict.update(decision="DEFER", reason="missing_expected_result")
        return verdict

    allowed_for_blocker = set(policy["blocker_work_classes"].get(blocker_id, []))
    if work_class not in allowed_for_blocker:
        verdict.update(decision="DEFER", reason="class_not_allowed_for_blocker")
        return verdict

    verdict.update(
        decision="ALLOW",
        reason="removes_or_measures_active_blocker",
        work_class=work_class,
        blocker=blocker_id,
        expected_result=result,
    )
    return verdict


def parse_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"invalid blocker override: {value!r}")
        key, state = value.split("=", 1)
        overrides[key.strip()] = state.strip().upper()
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/critical_path_policy.json")
    parser.add_argument("--event", help="GitHub pull_request event JSON")
    parser.add_argument("--body", help="PR body for local validation")
    parser.add_argument("--base", default=None)
    parser.add_argument("--blocker-state", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args()

    policy = load_json(args.policy)
    overrides = parse_overrides(args.blocker_state)

    body = args.body or ""
    base = args.base or policy["enforced_base_branch"]
    if args.event:
        event = load_json(args.event)
        pull_request = event.get("pull_request", {})
        body = pull_request.get("body") or ""
        base = pull_request.get("base", {}).get("ref") or base

    verdict = classify(policy, body, base_branch=base, overrides=overrides)
    rendered = json.dumps(verdict, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if verdict["decision"] == "ALLOW" else 78


if __name__ == "__main__":
    raise SystemExit(main())
