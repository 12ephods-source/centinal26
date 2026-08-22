from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

APP_HOME = Path(os.environ.get("SKYNET_HOME", str(Path.home() / ".skynet")))
DB = APP_HOME / "state.db"
KEY = APP_HOME / "secret.key"
CFG = APP_HOME / "config.json"
AUDIT = APP_HOME / "audit.jsonl"

DEFAULT_CFG = {
    "version": "0.1.0",
    "node_id": None,
    "allowed_tasks": ["health", "project_update", "snapshot", "verify"],
    "project_paths": {
        "automation": str(Path.home() / "centinal26"),
        "cybersecurity": str(Path.home() / "frost-sentinel"),
    },
    "protected_paths": [
        "evidence",
        "primary",
        "acquired",
        "vault",
        "cases",
        "originals",
        "forensic_images",
    ],
    "max_runtime_seconds": 300,
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256b(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_key() -> bytes:
    return KEY.read_bytes()


def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sign(obj) -> str:
    return hmac.new(read_key(), canon(obj), hashlib.sha256).hexdigest()


def audit(kind: str, data):
    APP_HOME.mkdir(parents=True, exist_ok=True)
    previous = "0" * 64
    if AUDIT.exists():
        try:
            previous = json.loads(AUDIT.read_text().splitlines()[-1])["hash"]
        except (OSError, IndexError, KeyError, json.JSONDecodeError):
            previous = "0" * 64
    record = {"ts": now(), "kind": kind, "data": data, "prev": previous}
    record["hash"] = sha256b(canon(record))
    with AUDIT.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def db():
    conn = sqlite3.connect(DB)
    conn.execute(
        "create table if not exists jobs("
        "id text primary key, type text, payload text, state text, "
        "created text, updated text, result text)"
    )
    conn.execute(
        "create table if not exists nodes("
        "node_id text primary key, last_seen text, meta text)"
    )
    conn.commit()
    return conn


def init() -> None:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    if not KEY.exists():
        KEY.write_bytes(os.urandom(32))
        os.chmod(KEY, 0o600)
    if not CFG.exists():
        config = dict(DEFAULT_CFG)
        config["node_id"] = str(uuid.uuid4())
        CFG.write_text(json.dumps(config, indent=2) + "\n")
    db().close()
    audit("init", {"home": str(APP_HOME)})
    print(APP_HOME)


def cfg():
    return json.loads(CFG.read_text())


def run_git(args: list[str], cwd: Path):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def git_state(path):
    root = Path(path)
    if not (root / ".git").exists():
        return {"ok": False, "reason": "not_git_repo", "path": str(root)}
    dirty = run_git(["status", "--porcelain"], root).stdout.strip()
    if dirty:
        return {"ok": False, "reason": "dirty_worktree", "path": str(root)}
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], root).stdout.strip()
    fetch = run_git(["fetch", "--prune", "origin", branch], root)
    if fetch.returncode:
        return {
            "ok": False,
            "reason": "fetch_failed",
            "stderr": fetch.stderr[-1000:],
        }
    head = run_git(["rev-parse", "HEAD"], root).stdout.strip()
    remote = run_git(["rev-parse", f"origin/{branch}"], root).stdout.strip()
    if head == remote:
        return {
            "ok": True,
            "action": "unchanged",
            "path": str(root),
            "branch": branch,
            "old": head,
            "remote": remote,
        }
    merge_base = run_git(["merge-base", head, remote], root)
    if merge_base.returncode:
        return {"ok": False, "reason": "merge_base_failed"}
    base = merge_base.stdout.strip()
    if base == head:
        return {
            "ok": True,
            "action": "fast_forward",
            "path": str(root),
            "branch": branch,
            "old": head,
            "remote": remote,
        }
    if base == remote:
        return {"ok": False, "reason": "local_ahead", "path": str(root)}
    return {"ok": False, "reason": "diverged", "path": str(root)}


def promote(state) -> bool:
    if state.get("action") != "fast_forward":
        return True
    root = Path(state["path"])
    result = run_git(["merge", "--ff-only", f"origin/{state['branch']}"], root)
    if result.returncode:
        return False
    state["new"] = run_git(["rev-parse", "HEAD"], root).stdout.strip()
    return state["new"] == state["remote"]


def rollback(state) -> None:
    if state.get("action") != "fast_forward" or not state.get("new"):
        return
    root = Path(state["path"])
    current = run_git(["rev-parse", "HEAD"], root).stdout.strip()
    if current == state["new"]:
        run_git(["reset", "--hard", state["old"]], root)
        state["rolled_back"] = True


def paired_project_update(project_paths):
    states = {name: git_state(path) for name, path in project_paths.items()}
    if not all(state.get("ok") for state in states.values()):
        return {"ok": False, "phase": "preflight", "projects": states}
    completed = []
    try:
        for name, state in states.items():
            if not promote(state):
                raise RuntimeError(f"promotion_failed:{name}")
            completed.append(state)
    except RuntimeError as exc:
        for state in reversed(completed):
            rollback(state)
        return {
            "ok": False,
            "phase": "promotion",
            "error": str(exc),
            "projects": states,
        }
    return {"ok": True, "phase": "complete", "projects": states}


def snapshot(config):
    output = APP_HOME / "snapshots" / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for name, raw_path in config["project_paths"].items():
        root = Path(raw_path)
        rows = []
        if root.exists():
            for path in root.rglob("*"):
                if not path.is_file() or ".git" in path.parts:
                    continue
                if any(part in config["protected_paths"] for part in path.parts):
                    continue
                try:
                    rows.append((str(path.relative_to(root)), sha256b(path.read_bytes())))
                except OSError:
                    continue
        manifest = output / f"{name}.sha256.json"
        manifest.write_text(json.dumps(rows, indent=2) + "\n")
        manifests[name] = str(manifest)
    return {"ok": True, "snapshot": str(output), "manifests": manifests}


def run_task(task_type: str, payload):
    config = cfg()
    if task_type not in config["allowed_tasks"]:
        return {"ok": False, "error": "task_not_allowed"}
    if task_type == "health":
        return {"ok": True, "node_id": config["node_id"], "ts": now()}
    if task_type == "verify":
        checks = {
            name: {
                "exists": Path(path).exists(),
                "git": (Path(path) / ".git").exists(),
            }
            for name, path in config["project_paths"].items()
        }
        return {"ok": all(item["exists"] for item in checks.values()), "checks": checks}
    if task_type == "project_update":
        return paired_project_update(config["project_paths"])
    if task_type == "snapshot":
        return snapshot(config)
    return {"ok": False, "error": "unimplemented"}


def submit(task_type: str, payload) -> None:
    config = cfg()
    job = {
        "id": str(uuid.uuid4()),
        "type": task_type,
        "payload": payload,
        "created": now(),
        "node_id": config["node_id"],
    }
    signature = sign(job)
    conn = db()
    conn.execute(
        "insert into jobs values(?,?,?,?,?,?,?)",
        (
            job["id"],
            task_type,
            json.dumps(payload),
            "queued",
            job["created"],
            job["created"],
            None,
        ),
    )
    conn.commit()
    conn.close()
    audit("job_submit", {"job": job, "sig": signature})
    print(json.dumps({"job": job, "sig": signature}, indent=2))


def work_once() -> None:
    conn = db()
    row = conn.execute(
        "select id,type,payload from jobs where state='queued' order by created limit 1"
    ).fetchone()
    if not row:
        conn.close()
        print(json.dumps({"ok": True, "idle": True}))
        return
    job_id, task_type, payload = row
    conn.execute(
        "update jobs set state='running',updated=? where id=?",
        (now(), job_id),
    )
    conn.commit()
    try:
        result = run_task(task_type, json.loads(payload))
        state = "done" if result.get("ok") else "failed"
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        result = {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
        state = "failed"
    conn.execute(
        "update jobs set state=?,updated=?,result=? where id=?",
        (state, now(), json.dumps(result), job_id),
    )
    conn.commit()
    conn.close()
    audit("job_result", {"id": job_id, "state": state, "result": result})
    print(json.dumps({"id": job_id, "state": state, "result": result}, indent=2))


def status() -> None:
    conn = db()
    jobs = conn.execute(
        "select id,type,state,created,updated,result from jobs "
        "order by created desc limit 20"
    ).fetchall()
    conn.close()
    rendered = []
    for row in jobs:
        rendered.append(
            {
                "id": row[0],
                "type": row[1],
                "state": row[2],
                "created": row[3],
                "updated": row[4],
                "result": json.loads(row[5]) if row[5] else None,
            }
        )
    print(json.dumps({"config": cfg(), "jobs": rendered}, indent=2))


def verify_audit() -> None:
    previous = "0" * 64
    valid = True
    count = 0
    if AUDIT.exists():
        for line in AUDIT.read_text().splitlines():
            record = json.loads(line)
            stored_hash = record.pop("hash")
            valid &= record.get("prev") == previous and sha256b(canon(record)) == stored_hash
            previous = stored_hash
            count += 1
    print(json.dumps({"ok": bool(valid), "records": count, "head": previous}, indent=2))
    sys.exit(0 if valid else 2)


def main() -> None:
    parser = argparse.ArgumentParser(prog="skynet")
    commands = parser.add_subparsers(dest="cmd", required=True)
    commands.add_parser("init")
    submit_parser = commands.add_parser("submit")
    submit_parser.add_argument("type")
    submit_parser.add_argument("--payload", default="{}")
    commands.add_parser("work-once")
    commands.add_parser("status")
    commands.add_parser("verify-audit")
    args = parser.parse_args()
    if args.cmd == "init":
        init()
    elif args.cmd == "submit":
        submit(args.type, json.loads(args.payload))
    elif args.cmd == "work-once":
        work_once()
    elif args.cmd == "status":
        status()
    elif args.cmd == "verify-audit":
        verify_audit()


if __name__ == "__main__":
    main()
