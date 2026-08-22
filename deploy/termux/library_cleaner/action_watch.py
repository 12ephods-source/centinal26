"""Strict action-only watcher for the Centinal26 GitHub workstream.

Uses an authenticated GitHub CLI when available. It persists a compact prior
snapshot and emits only state transitions that require operator action. Local
release/device gate JSON files are also folded into the same evidence model.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

APP = Path.home() / ".local" / "share" / "frost-library-cleaner"
STATE = APP / "action-watch-state.json"
STATUS = APP / "autopilot-status.json"
DEFAULT_REPO = "12ephods-source/centinal26"


def run_json(args: list[str]) -> Any:
    result = subprocess.run(args, capture_output=True, text=True, timeout=45, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "command failed").strip())
    return json.loads(result.stdout)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def github_snapshot(repo: str) -> dict[str, Any]:
    pulls = run_json(["gh", "api", f"repos/{repo}/pulls?state=open&per_page=100"])
    runs = run_json(["gh", "api", f"repos/{repo}/actions/runs?per_page=100"])
    pr_state = {
        str(pr["number"]): {
            "title": pr.get("title", ""),
            "draft": bool(pr.get("draft")),
            "updated_at": pr.get("updated_at"),
            "head_sha": (pr.get("head") or {}).get("sha"),
        }
        for pr in pulls
    }
    run_state: dict[str, Any] = {}
    for run in runs.get("workflow_runs", []):
        key = f"{run.get('name')}:{run.get('head_branch')}"
        if key not in run_state:
            run_state[key] = {
                "id": run.get("id"),
                "name": run.get("name"),
                "branch": run.get("head_branch"),
                "event": run.get("event"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "head_sha": run.get("head_sha"),
                "updated_at": run.get("updated_at"),
                "html_url": run.get("html_url"),
            }
    return {"pull_requests": pr_state, "workflow_runs": run_state}


def gate_snapshot() -> dict[str, Any]:
    return {
        "release_gate": load_json(APP / "release-gate.json", None),
        "device_validation": load_json(APP / "device-validation.json", None),
    }


def evidence_state(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, dict):
        raw = str(value.get("evidence_state") or value.get("state") or value.get("status") or "").upper()
        if raw:
            return raw
    return "OBSERVED"


def actionable_changes(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    old_runs = previous.get("github", {}).get("workflow_runs", {})
    new_runs = current.get("github", {}).get("workflow_runs", {})
    for key, run in new_runs.items():
        old = old_runs.get(key, {})
        conclusion = run.get("conclusion")
        old_conclusion = old.get("conclusion")
        if conclusion in {"failure", "cancelled", "timed_out", "action_required"} and conclusion != old_conclusion:
            changes.append({
                "kind": "CI",
                "affected_item": key,
                "change": f"workflow conclusion changed from {old_conclusion or 'unknown'} to {conclusion}",
                "evidence_state": "OBSERVED_GITHUB",
                "next_step": "Open the first failing job, identify the earliest causal failure, and apply the smallest isolated repair.",
                "url": run.get("html_url"),
            })
    old_prs = previous.get("github", {}).get("pull_requests", {})
    new_prs = current.get("github", {}).get("pull_requests", {})
    for number, pr in new_prs.items():
        old = old_prs.get(number)
        if old and old.get("head_sha") != pr.get("head_sha"):
            changes.append({
                "kind": "PR",
                "affected_item": f"PR #{number}: {pr.get('title', '')}",
                "change": "head commit changed",
                "evidence_state": "OBSERVED_GITHUB",
                "next_step": "Re-evaluate required checks and mergeability on the new head; ignore if all gates remain green.",
            })
    for gate_name in ("release_gate", "device_validation"):
        old = previous.get("gates", {}).get(gate_name)
        new = current.get("gates", {}).get(gate_name)
        if old != new and new is not None:
            state = evidence_state(new)
            if any(token in state for token in ("BLOCK", "FAIL", "PENDING", "ACTION", "REJECT")):
                changes.append({
                    "kind": "GATE",
                    "affected_item": gate_name,
                    "change": "gate/blocker state changed",
                    "evidence_state": state,
                    "next_step": "Satisfy the narrowest missing evidence requirement without weakening the gate or substituting inferred evidence.",
                })
    return changes


def check(repo: str) -> dict[str, Any]:
    previous = load_json(STATE, {})
    errors: list[str] = []
    try:
        github = github_snapshot(repo)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        github = previous.get("github", {})
        errors.append(f"github_unavailable:{exc}")
    current = {
        "schema": "centinal26.autopilot.action-watch.v1",
        "checked_at": time.time(),
        "repo": repo,
        "github": github,
        "gates": gate_snapshot(),
    }
    changes = actionable_changes(previous, current) if previous else []
    status = {
        "schema": "centinal26.autopilot.status.v1",
        "updated_at": current["checked_at"],
        "repo": repo,
        "mode": "STRICT_ACTION_ONLY",
        "actionable_count": len(changes),
        "actionable_changes": changes,
        "evidence_errors": errors,
        "watch_state": "ACTION_REQUIRED" if changes else ("DEGRADED" if errors else "QUIET"),
    }
    atomic_write(STATE, current)
    atomic_write(STATUS, status)
    return status


def emit(status: dict[str, Any], force_json: bool) -> int:
    if force_json or status["actionable_count"]:
        print(json.dumps(status, indent=2, sort_keys=True))
    return 2 if status["actionable_count"] else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("CENTINAL26_REPO", DEFAULT_REPO))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--loop", action="store_true", help="repeat checks until interrupted")
    parser.add_argument("--interval", type=int, default=3600, help="loop interval in seconds; minimum 60")
    args = parser.parse_args()
    interval = max(60, args.interval)
    if not args.loop:
        return emit(check(args.repo), args.json)
    try:
        while True:
            emit(check(args.repo), args.json)
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
