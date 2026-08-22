from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PAIR_ID = "frost-cybersecurity-automation"
PROTECTED_CYBER = {
    "evidence",
    "primary",
    "acquired",
    "vault",
    "cases",
    "originals",
    "forensic_images",
}


def run(cmd, cwd=None, check=True):
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_manifest(root: Path, exclude_top=frozenset()):
    rows = []
    if not root.exists():
        return rows
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in exclude_top:
            continue
        if ".git" in rel.parts:
            continue
        rows.append(
            {
                "path": str(rel),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )
    return rows


def git_state(root: Path, branch: str):
    if not (root / ".git").exists():
        return {
            "root": str(root),
            "git": False,
            "branch": branch,
            "action": "local_only",
        }
    dirty = run(["git", "status", "--porcelain"], root)
    if dirty:
        raise RuntimeError(f"dirty worktree: {root}")
    head = run(["git", "rev-parse", "HEAD"], root)
    run(["git", "fetch", "--prune", "origin", branch], root)
    remote = run(["git", "rev-parse", f"origin/{branch}"], root)
    if head == remote:
        action = "unchanged"
    else:
        base = run(["git", "merge-base", head, remote], root)
        if base == head:
            action = "fast_forward"
        elif base == remote:
            raise RuntimeError(f"local branch ahead of origin/{branch}: {root}")
        else:
            raise RuntimeError(f"local branch diverged from origin/{branch}: {root}")
    return {
        "root": str(root),
        "git": True,
        "branch": branch,
        "old": head,
        "remote": remote,
        "action": action,
    }


def promote(state):
    if state.get("action") != "fast_forward":
        return
    root = Path(state["root"])
    run(["git", "merge", "--ff-only", f"origin/{state['branch']}"], root)
    current = run(["git", "rev-parse", "HEAD"], root)
    if current != state["remote"]:
        raise RuntimeError(f"unexpected post-merge HEAD: {root}")
    state["new"] = current


def rollback(state):
    if state.get("action") != "fast_forward" or not state.get("new"):
        return
    root = Path(state["root"])
    current = run(["git", "rev-parse", "HEAD"], root)
    if current == state["new"]:
        run(["git", "reset", "--hard", state["old"]], root)
        state["rolled_back"] = True


def safe_copy_tree(src: Path, dst: Path, *, exclude_top=frozenset()):
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return 0
    count = 0
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if not rel.parts:
            continue
        if rel.parts[0] in exclude_top or ".git" in rel.parts:
            continue
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            count += 1
    return count


def choose_export(root: Path, names):
    for name in names:
        path = root / name
        if path.exists() and path.is_dir():
            return path
    return root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--automation-root",
        default=os.environ.get("FROST_AUTOMATION_ROOT", str(Path.home() / "centinal26")),
    )
    parser.add_argument(
        "--cybersecurity-root",
        default=os.environ.get(
            "FROST_CYBERSECURITY_ROOT",
            str(Path.home() / "Frost_Sentinel_Cybersecurity"),
        ),
    )
    parser.add_argument(
        "--automation-branch",
        default=os.environ.get("FROST_AUTOMATION_BRANCH", "main"),
    )
    parser.add_argument(
        "--cybersecurity-branch",
        default=os.environ.get("FROST_CYBERSECURITY_BRANCH", "main"),
    )
    parser.add_argument(
        "--state-root",
        default=os.environ.get("FROST_PAIR_STATE", str(Path.home() / ".frost_project_pair")),
    )
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    auto = Path(args.automation_root).expanduser().resolve()
    cyber = Path(args.cybersecurity_root).expanduser().resolve()
    state = Path(args.state_root).expanduser().resolve()
    state.mkdir(parents=True, exist_ok=True)
    receipts = state / "receipts"
    receipts.mkdir(exist_ok=True)
    lock = state / "update.lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        print(
            f"pair updater already running or lock unavailable: {exc}",
            file=sys.stderr,
        )
        return 75

    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    record = {
        "schema": 1,
        "pair_id": PAIR_ID,
        "timestamp_utc": timestamp,
        "automation_root": str(auto),
        "cybersecurity_root": str(cyber),
        "status": "STARTED",
    }
    try:
        states = [
            git_state(auto, args.automation_branch),
            git_state(cyber, args.cybersecurity_branch),
        ]
        record["preflight"] = states
        if not args.status_only:
            done = []
            try:
                for item in states:
                    promote(item)
                    done.append(item)
            except RuntimeError:
                for item in reversed(done):
                    rollback(item)
                raise

        auto_export = choose_export(auto, ["exports/cybersecurity_shared", "shared"])
        cyber_export = choose_export(cyber, ["exports/automation_shared", "shared"])
        pair = state / "integrated"
        auto_count = safe_copy_tree(
            auto_export,
            pair / "automation_for_cybersecurity",
        )
        cyber_count = safe_copy_tree(
            cyber_export,
            pair / "cybersecurity_for_automation",
            exclude_top=PROTECTED_CYBER,
        )
        cyber_integration = cyber / "integrations" / "automation"
        if not args.status_only:
            safe_copy_tree(auto_export, cyber_integration)
        manifests = {
            "automation_for_cybersecurity": tree_manifest(
                pair / "automation_for_cybersecurity"
            ),
            "cybersecurity_for_automation": tree_manifest(
                pair / "cybersecurity_for_automation",
                exclude_top=PROTECTED_CYBER,
            ),
        }
        record.update(
            {
                "status": "PASS",
                "copied": {
                    "automation": auto_count,
                    "cybersecurity": cyber_count,
                },
                "manifests": manifests,
            }
        )
    except (OSError, RuntimeError, ValueError) as exc:
        record.update({"status": "FAIL", "error": str(exc)})

    output = receipts / f"{timestamp}__pair_update_receipt.json"
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    digest = sha256_file(output)
    output.with_suffix(".json.sha256").write_text(f"{digest}  {output.name}\n")
    print(
        json.dumps(
            {"status": record["status"], "receipt": str(output), "sha256": digest},
            indent=2,
        )
    )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
