"""Centinal26 bounded Android/Termux execution daemon.

This worker is intentionally local-first and fail-closed. It consumes only structured
operations from its durable SQLite queue, resolves them through an explicit capability
registry, executes bounded adapters, records provenance, and reconciles stale leases.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(os.environ.get("CENTINAL26_HOME", str(Path.home() / ".centinal26")))
STATE = ROOT / "state"
LOGS = ROOT / "logs"
CONFIG = ROOT / "config"
DB = STATE / "daemon.sqlite3"
STOP = STATE / "STOP"

for p in (STATE, LOGS, CONFIG):
    p.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("centinal26-daemon")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = RotatingFileHandler(LOGS / "daemon.log", maxBytes=2_000_000, backupCount=5)
    h.setFormatter(logging.Formatter("%(asctime)sZ %(levelname)s %(message)s"))
    logger.addHandler(h)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
CREATE TABLE IF NOT EXISTS task (
  id TEXT PRIMARY KEY,
  intent TEXT NOT NULL,
  capability TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  state TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  lease_owner TEXT,
  lease_until INTEGER,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  next_attempt_at INTEGER NOT NULL DEFAULT 0,
  source_revision TEXT,
  last_error TEXT
);
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES task(id)
);
CREATE TABLE IF NOT EXISTS daemon_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def digest_obj(obj: object) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def evidence(con: sqlite3.Connection, task_id: str, kind: str, payload: dict) -> None:
    rec = {"task_id": task_id, "kind": kind, "payload": payload}
    con.execute(
        "INSERT INTO evidence(task_id,ts,kind,payload_json,sha256) VALUES(?,?,?,?,?)",
        (task_id, int(time.time()), kind, json.dumps(payload, sort_keys=True), digest_obj(rec)),
    )


@dataclass(frozen=True)
class Capability:
    name: str
    handler: Callable[[dict], dict]
    verify: Callable[[dict, dict], dict]


def run(argv: list[str], timeout: int = 120, cwd: str | None = None) -> dict:
    started = time.time()
    cp = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        check=False,
    )
    return {
        "argv": argv,
        "returncode": cp.returncode,
        "stdout": cp.stdout[-20000:],
        "stderr": cp.stderr[-20000:],
        "duration_s": round(time.time() - started, 3),
    }


def local_script(payload: dict) -> dict:
    path = Path(payload["path"]).expanduser().resolve()
    allowed_roots = [ROOT.resolve(), (Path.home() / "centinal26").resolve()]
    if not any(str(path).startswith(str(root) + os.sep) or path == root for root in allowed_roots):
        raise ValueError("script path outside approved roots")
    if not path.is_file():
        raise FileNotFoundError(path)
    expected = payload.get("sha256")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if not expected or expected != actual:
        raise ValueError("script hash missing or mismatched")
    args = payload.get("args", [])
    if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
        raise ValueError("args must be string list")
    if path.suffix == ".py":
        argv = [sys.executable, str(path), *args]
    elif path.suffix in {".sh", ".bash"}:
        argv = ["bash", str(path), *args]
    else:
        raise ValueError("unsupported script type")
    return run(argv, timeout=min(int(payload.get("timeout", 120)), 900), cwd=str(path.parent))


def github_cli(payload: dict) -> dict:
    op = payload.get("op")
    repo = payload.get("repo")
    if not repo or "/" not in repo:
        raise ValueError("repo required")
    if op == "pr_checks":
        number = str(int(payload["number"]))
        return run(["gh", "pr", "checks", number, "--repo", repo], timeout=120)
    if op == "issue_view":
        number = str(int(payload["number"]))
        return run(
            ["gh", "issue", "view", number, "--repo", repo, "--json", "number,title,state,labels,updatedAt"],
            timeout=120,
        )
    if op == "repo_sync":
        path = Path(payload.get("path", str(Path.home() / "centinal26"))).expanduser().resolve()
        return run(["git", "-C", str(path), "fetch", "--ff-only", "origin"], timeout=120)
    raise ValueError("unsupported github operation")


def provider_adapter(payload: dict) -> dict:
    """Invoke a locally configured provider adapter through an explicit capability."""
    cfg_path = CONFIG / "providers.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {"providers": {}}
    provider = payload.get("provider")
    capability = payload.get("capability")
    p = cfg.get("providers", {}).get(provider)
    if not p or capability not in p.get("capabilities", []):
        raise ValueError("provider/capability not configured")
    exe = Path(p["executable"]).expanduser().resolve()
    if not exe.is_file():
        raise FileNotFoundError(exe)
    request = payload.get("request", {})
    raw = json.dumps(request, sort_keys=True)
    cp = subprocess.run(
        [str(exe), capability],
        input=raw,
        text=True,
        capture_output=True,
        timeout=min(int(payload.get("timeout", 120)), 900),
        check=False,
    )
    return {
        "provider": provider,
        "capability": capability,
        "returncode": cp.returncode,
        "stdout": cp.stdout[-20000:],
        "stderr": cp.stderr[-20000:],
    }


def verify_returncode(_payload: dict, result: dict) -> dict:
    ok = result.get("returncode") == 0
    return {
        "status": "PASS" if ok else "FAIL",
        "basis": "returncode",
        "returncode": result.get("returncode"),
    }


CAPS = {
    "local.script": Capability("local.script", local_script, verify_returncode),
    "github.cli": Capability("github.cli", github_cli, verify_returncode),
    "provider.invoke": Capability("provider.invoke", provider_adapter, verify_returncode),
}


def recover(con: sqlite3.Connection) -> None:
    now = int(time.time())
    con.execute(
        "UPDATE task SET state='RETRY_WAIT', lease_owner=NULL, lease_until=NULL, next_attempt_at=?, updated_at=? "
        "WHERE state='RUNNING' AND lease_until IS NOT NULL AND lease_until < ?",
        (now, now, now),
    )


def claim(con: sqlite3.Connection, worker: str) -> sqlite3.Row | None:
    now = int(time.time())
    con.execute("BEGIN IMMEDIATE")
    try:
        row = con.execute(
            "SELECT * FROM task WHERE state IN ('QUEUED','RETRY_WAIT') AND next_attempt_at<=? ORDER BY created_at LIMIT 1",
            (now,),
        ).fetchone()
        if row is None:
            con.execute("COMMIT")
            return None
        lease_until = now + 300
        changed = con.execute(
            "UPDATE task SET state='RUNNING', lease_owner=?, lease_until=?, attempt_count=attempt_count+1, updated_at=? "
            "WHERE id=? AND state IN ('QUEUED','RETRY_WAIT')",
            (worker, lease_until, now, row["id"]),
        ).rowcount
        if changed != 1:
            con.execute("ROLLBACK")
            return None
        con.execute("COMMIT")
        return con.execute("SELECT * FROM task WHERE id=?", (row["id"],)).fetchone()
    except sqlite3.Error:
        con.execute("ROLLBACK")
        raise


def execute_one(con: sqlite3.Connection, row: sqlite3.Row, worker: str) -> None:
    task_id = row["id"]
    payload = json.loads(row["payload_json"])
    cap = CAPS.get(row["capability"])
    if cap is None:
        err = "capability not registered"
        evidence(con, task_id, "execution", {"status": "FAIL", "error": err})
        con.execute(
            "UPDATE task SET state='FAILED',last_error=?,updated_at=? WHERE id=?",
            (err, int(time.time()), task_id),
        )
        return
    evidence(
        con,
        task_id,
        "execution_start",
        {"worker": worker, "capability": cap.name, "payload_sha256": digest_obj(payload)},
    )
    try:
        result = cap.handler(payload)
        evidence(con, task_id, "execution_result", result)
        verdict = cap.verify(payload, result)
        evidence(con, task_id, "verification", verdict)
        state = "VERIFIED" if verdict.get("status") == "PASS" else "FAILED"
        con.execute(
            "UPDATE task SET state=?,lease_owner=NULL,lease_until=NULL,last_error=NULL,updated_at=? WHERE id=?",
            (state, int(time.time()), task_id),
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        attempts = int(row["attempt_count"]) + 1
        if attempts < 5:
            delay = min(900, (2**attempts) * 5 + random.randint(0, 7))
            state = "RETRY_WAIT"
            next_at = int(time.time()) + delay
        else:
            state = "FAILED"
            next_at = 0
        msg = f"{type(exc).__name__}: {exc}"
        evidence(
            con,
            task_id,
            "execution_error",
            {"error": msg, "attempt": attempts, "next_attempt_at": next_at},
        )
        con.execute(
            "UPDATE task SET state=?,lease_owner=NULL,lease_until=NULL,next_attempt_at=?,last_error=?,updated_at=? WHERE id=?",
            (state, next_at, msg, int(time.time()), task_id),
        )


def health(con: sqlite3.Connection, worker: str) -> None:
    payload = {
        "worker": worker,
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "root": str(ROOT),
        "capabilities": sorted(CAPS),
        "ts": int(time.time()),
    }
    con.execute(
        "INSERT OR REPLACE INTO daemon_state(key,value) VALUES('health',?)",
        (json.dumps(payload, sort_keys=True),),
    )


def main() -> int:
    worker = f"termux:{os.uname().nodename}:{os.getpid()}"
    con = connect()
    logger.info("daemon_start worker=%s", worker)
    last_health = 0.0
    while not STOP.exists():
        recover(con)
        if time.time() - last_health >= 30:
            health(con, worker)
            last_health = time.time()
        row = claim(con, worker)
        if row is None:
            time.sleep(2)
            continue
        execute_one(con, row, worker)
    logger.info("daemon_stop worker=%s", worker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
