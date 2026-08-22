from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def reconcile(repo: Path, state_path: Path) -> dict[str, object]:
    current_head = git(repo, "rev-parse", "HEAD")
    main_head = git(repo, "rev-parse", "origin/main")
    state = json.loads(state_path.read_text())
    recorded = state.get("release")
    stale = recorded != main_head
    checks = dict(state.get("checks", {}))
    software_required = (
        "repo_sync",
        "repo_clean",
        "pair_ok",
        "skynet_ok",
        "state_integrity_ok",
        "recovery_ok",
        "security_policy_ok",
    )
    deployment_required = software_required + (
        "device_boot_ok",
        "device_restart_ok",
        "device_exec_ok",
        "device_audit_ok",
    )
    software_complete = (not stale) and all(bool(checks.get(k, False)) for k in software_required)
    deployed_complete = (not stale) and all(bool(checks.get(k, False)) for k in deployment_required)
    return {
        "current_head": current_head,
        "main_head": main_head,
        "recorded_release": recorded,
        "stale_release": stale,
        "software_release_complete": software_complete,
        "deployed_app_complete": deployed_complete,
        "software_missing": [k for k in software_required if not bool(checks.get(k, False))],
        "deployment_missing": [k for k in deployment_required if not bool(checks.get(k, False))],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--state", required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile(Path(args.repo), Path(args.state)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
