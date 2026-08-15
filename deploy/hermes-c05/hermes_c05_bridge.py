#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import secrets
import sqlite3
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

VERSION = "1.0.0"
SCHEMA = "frost-call/1.0"
HOME = pathlib.Path(os.environ.get("HERMES_C05_HOME", "~/.local/state/hermes-c05")).expanduser()
CENTINAL26_HOME = pathlib.Path(
    os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26")
).expanduser()
REQUESTS = HOME / "requests"
RESULTS = HOME / "results"
AUDIT = HOME / "audit.jsonl"
DB = HOME / "bridge.sqlite3"

# Model-callable automatic execution is deliberately narrow.
AUTO_CAPABILITIES = {"system.echo"}
GITHUB_AUTO_OPERATIONS = {
    "system.health",
    "system.capabilities",
    "frost.diagnostics.echo",
    "frost.diagnostics.sha256",
    "frost.diagnostics.canonicalize",
}
MODEL_AUTO_CAPABILITIES = AUTO_CAPABILITIES | GITHUB_AUTO_OPERATIONS


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def ensure_layout() -> None:
    for path in (HOME, REQUESTS, RESULTS):
        path.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS grants (
              token_hash TEXT PRIMARY KEY,
              capability TEXT NOT NULL,
              expires_at REAL NOT NULL,
              used_at REAL,
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS calls (
              request_id TEXT PRIMARY KEY,
              request_hash TEXT NOT NULL,
              capability TEXT NOT NULL,
              caller TEXT NOT NULL,
              provider TEXT NOT NULL,
              status TEXT NOT NULL,
              job_id TEXT,
              result_json TEXT,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL
            );
            """
        )


def audit(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_layout()
    prev = "0" * 64
    if AUDIT.exists():
        lines = AUDIT.read_text(encoding="utf-8").splitlines()
        if lines:
            prev = json.loads(lines[-1])["hash"]
    body = {
        "timestamp": now_iso(),
        "event": event,
        "payload": payload,
        "previous_hash": prev,
    }
    body["hash"] = hashlib.sha256(canonical(body)).hexdigest()
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(body, sort_keys=True, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return body


def verify_audit() -> bool:
    if not AUDIT.exists():
        return True
    prev = "0" * 64
    for line in AUDIT.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        found = row.pop("hash")
        if row["previous_hash"] != prev:
            return False
        if hashlib.sha256(canonical(row)).hexdigest() != found:
            return False
        prev = found
    return True


def load_engine():
    os.environ["CENTINAL26_HOME"] = str(CENTINAL26_HOME)
    from centinal26.cli import engine as build_engine  # type: ignore
    from centinal26.core import Grant  # type: ignore

    return build_engine(), Grant


def engine_capabilities() -> set[str]:
    runtime, _ = load_engine()
    return set(runtime.capabilities)


def make_envelope(
    capability: str,
    arguments: dict[str, Any],
    *,
    request_id: str,
    caller: str,
    source: str = "hermes",
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "target": capability,
        "input": arguments,
        "context": {
            "request_id": request_id,
            "idempotency_key": request_id,
            "project": "Hermes",
            "source": source,
            "authorization_context": {
                "caller": caller,
                "automatic": capability in MODEL_AUTO_CAPABILITIES,
            },
        },
    }


def issue_user_grant(capability: str, ttl: int) -> str:
    if ttl < 30 or ttl > 3600:
        raise ValueError("ttl must be between 30 and 3600 seconds")
    available = engine_capabilities()
    if capability not in available:
        raise ValueError(f"unknown C05 capability: {capability}")
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    ensure_layout()
    with sqlite3.connect(DB) as db:
        db.execute(
            "INSERT INTO grants(token_hash,capability,expires_at,used_at,created_at) "
            "VALUES(?,?,?,?,?)",
            (digest, capability, now + ttl, None, now),
        )
        db.commit()
    audit(
        "user_grant_issued",
        {
            "capability": capability,
            "token_hash": digest,
            "expires_at": now + ttl,
        },
    )
    return token


def consume_grant(capability: str, token: str) -> None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    ensure_layout()
    with sqlite3.connect(DB) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT capability,expires_at,used_at FROM grants WHERE token_hash=?",
            (digest,),
        ).fetchone()
        if not row:
            raise PermissionError("approval token not found")
        if row[0] != capability:
            raise PermissionError("approval token capability mismatch")
        if row[2] is not None:
            raise PermissionError("approval token already used")
        if float(row[1]) <= now:
            raise PermissionError("approval token expired")
        db.execute(
            "UPDATE grants SET used_at=? WHERE token_hash=?",
            (now, digest),
        )
        db.commit()
    audit("user_grant_consumed", {"capability": capability, "token_hash": digest})


def _job_row(runtime, job_id: str):
    return runtime.store.connection.execute(
        "SELECT * FROM jobs WHERE id=?",
        (job_id,),
    ).fetchone()


def execute_local(
    envelope: dict[str, Any],
    *,
    caller: str,
    approval_token: str | None,
    user_approved: bool,
) -> dict[str, Any]:
    capability = str(envelope["target"])
    arguments = envelope.get("input") or {}
    if not isinstance(arguments, dict):
        raise ValueError("input must be an object")

    runtime, Grant = load_engine()
    if capability not in runtime.capabilities:
        raise KeyError(f"C05 capability is not registered: {capability}")

    if capability not in AUTO_CAPABILITIES:
        if not user_approved:
            raise PermissionError(
                "non-A0 capability requires direct user CLI approval; "
                "model-callable Hermes tools cannot self-authorize it"
            )
        if not approval_token:
            raise PermissionError("approval token required")
        consume_grant(capability, approval_token)

    expires = datetime.now(UTC) + timedelta(minutes=5)
    grant = Grant(
        grant_id=str(uuid.uuid4()),
        capability=capability,
        expires_at=expires.isoformat(),
    )
    job_id = runtime.submit(capability, arguments, grant)
    runtime.run_once()
    row = _job_row(runtime, job_id)
    if row is None:
        raise RuntimeError("C05 job disappeared after execution")

    raw_result = row["result"]
    parsed_result = json.loads(raw_result) if raw_result else None
    result = {
        "schema": SCHEMA,
        "provider": "local-c05",
        "request_id": envelope["context"]["request_id"],
        "request_hash": sha256_obj(envelope),
        "capability": capability,
        "job_id": job_id,
        "state": row["state"],
        "result": parsed_result,
        "verified": row["state"] == "verified",
        "audit_valid": runtime.audit.verify(),
        "completed_at": now_iso(),
    }
    result["result_hash"] = sha256_obj(result)
    return result


def stage_connected(envelope: dict[str, Any]) -> dict[str, Any]:
    """Translate the core envelope into the current GitHub provider request.

    The file is staged locally only. No GitHub mutation occurs here.
    """
    ensure_layout()
    operation = str(envelope["target"])
    if operation not in GITHUB_AUTO_OPERATIONS:
        raise PermissionError(
            "model-callable GitHub staging is limited to the connected provider's "
            "read-only operation allowlist"
        )
    request_id = envelope["context"]["request_id"]
    provider_request = {
        "protocol": SCHEMA,
        "kind": "invoke",
        "idempotency_key": request_id,
        "service_id": "frost.callable.fabric",
        "operation": operation,
        "arguments": envelope.get("input") or {},
        "context": {
            "caller": "hermes-c05",
            "role": "operator",
            "approved": False,
            "request_id": request_id,
            "source": "hermes",
        },
    }
    path = REQUESTS / f"{request_id}.json"
    rendered = (
        json.dumps(provider_request, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != rendered:
            raise RuntimeError("request_id already exists with different content")
        reused = True
    else:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(rendered, encoding="utf-8")
        with tmp.open("r+") as f:
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        reused = False
    record = {
        "schema": SCHEMA,
        "provider": "github-actions",
        "status": "STAGED_LOCAL_ONLY",
        "request_id": request_id,
        "request_hash": sha256_obj(envelope),
        "provider_request_hash": sha256_obj(provider_request),
        "operation": operation,
        "path": str(path),
        "reused": reused,
        "note": (
            "No GitHub write was performed. Publish through the separately "
            "authorized connected-provider workflow."
        ),
    }
    audit("connected_request_staged", record)
    return record


def record_call(
    request_id: str,
    envelope: dict[str, Any],
    caller: str,
    provider: str,
    status: str,
    result: dict[str, Any] | None,
) -> None:
    ensure_layout()
    now = time.time()
    with sqlite3.connect(DB) as db:
        db.execute(
            """
            INSERT INTO calls(
              request_id,request_hash,capability,caller,provider,status,
              job_id,result_json,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(request_id) DO UPDATE SET
              status=excluded.status,
              job_id=excluded.job_id,
              result_json=excluded.result_json,
              updated_at=excluded.updated_at
            """,
            (
                request_id,
                sha256_obj(envelope),
                envelope["target"],
                caller,
                provider,
                status,
                result.get("job_id") if result else None,
                json.dumps(result, sort_keys=True) if result else None,
                now,
                now,
            ),
        )
        db.commit()


def call(
    capability: str,
    arguments: dict[str, Any],
    *,
    caller: str,
    provider: str,
    request_id: str | None = None,
    approval_token: str | None = None,
    user_approved: bool = False,
) -> dict[str, Any]:
    request_id = request_id or str(uuid.uuid4())
    envelope = make_envelope(
        capability,
        arguments,
        request_id=request_id,
        caller=caller,
    )
    audit(
        "call_requested",
        {
            "request_id": request_id,
            "request_hash": sha256_obj(envelope),
            "capability": capability,
            "caller": caller,
            "provider": provider,
        },
    )
    try:
        if provider == "local":
            result = execute_local(
                envelope,
                caller=caller,
                approval_token=approval_token,
                user_approved=user_approved,
            )
        elif provider == "github":
            result = stage_connected(envelope)
        else:
            raise ValueError("provider must be local or github")
        record_call(
            request_id,
            envelope,
            caller,
            provider,
            result["status"] if "status" in result else result.get("state", "UNKNOWN"),
            result,
        )
        audit(
            "call_completed",
            {
                "request_id": request_id,
                "provider": provider,
                "result_hash": sha256_obj(result),
            },
        )
        return result
    except Exception as exc:
        record_call(request_id, envelope, caller, provider, "FAILED", None)
        audit(
            "call_failed",
            {
                "request_id": request_id,
                "provider": provider,
                "error": type(exc).__name__,
                "message": str(exc),
            },
        )
        raise


def status() -> dict[str, Any]:
    ensure_layout()
    available: list[str] = []
    engine_error = None
    try:
        available = sorted(engine_capabilities())
    except Exception as exc:
        engine_error = f"{type(exc).__name__}: {exc}"
    with sqlite3.connect(DB) as db:
        calls = db.execute(
            "SELECT status,COUNT(*) FROM calls GROUP BY status ORDER BY status"
        ).fetchall()
    return {
        "version": VERSION,
        "schema": SCHEMA,
        "home": str(HOME),
        "centinal26_home": str(CENTINAL26_HOME),
        "auto_capabilities": sorted(AUTO_CAPABILITIES),
        "registered_capabilities": available,
        "engine_error": engine_error,
        "call_counts": {row[0]: row[1] for row in calls},
        "audit_valid": verify_audit(),
    }


def selftest() -> dict[str, Any]:
    ensure_layout()
    # Do not require Centinal26 for pure bridge invariants.
    sample = make_envelope(
        "frost.diagnostics.echo",
        {"text": "test"},
        request_id="selftest-001",
        caller="selftest",
    )
    assert sample["schema"] == SCHEMA
    assert sample["context"]["authorization_context"]["automatic"] is True

    staged = stage_connected(sample)
    assert staged["status"] == "STAGED_LOCAL_ONLY"
    staged2 = stage_connected(sample)
    assert staged2["reused"] is True
    assert verify_audit()

    token = secrets.token_urlsafe(16)
    assert hashlib.sha256(token.encode()).hexdigest()
    return {
        "status": "PASS",
        "schema": True,
        "immutable_staging": True,
        "idempotent_staging": True,
        "audit_chain": True,
        "no_external_publish": True,
        "model_auto_capabilities": sorted(MODEL_AUTO_CAPABILITIES),
    }


def parse_json_arg(value: str) -> dict[str, Any]:
    if value == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("arguments JSON must be an object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(prog="hermes-c05")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")
    sub.add_parser("selftest")
    sub.add_parser("verify-audit")

    p = sub.add_parser("grant")
    p.add_argument("capability")
    p.add_argument("--ttl", type=int, default=300)

    p = sub.add_parser("call")
    p.add_argument("capability")
    p.add_argument("--json", default="{}")
    p.add_argument("--provider", choices=["local", "github"], default="local")
    p.add_argument("--request-id")
    p.add_argument("--approval-token")
    p.add_argument(
        "--user-approve",
        action="store_true",
        help="Direct CLI assertion; never set by the model-callable Hermes plugin.",
    )

    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(status(), indent=2, sort_keys=True))
        return 0
    if args.command == "selftest":
        print(json.dumps(selftest(), indent=2, sort_keys=True))
        return 0
    if args.command == "verify-audit":
        ok = verify_audit()
        print(json.dumps({"audit_valid": ok}, sort_keys=True))
        return 0 if ok else 1
    if args.command == "grant":
        token = issue_user_grant(args.capability, args.ttl)
        print(
            json.dumps(
                {
                    "capability": args.capability,
                    "approval_token": token,
                    "ttl_seconds": args.ttl,
                    "warning": "Token is single-use. Do not paste it into model context.",
                },
                indent=2,
            )
        )
        return 0
    if args.command == "call":
        data = parse_json_arg(args.json)
        result = call(
            args.capability,
            data,
            caller="direct-user-cli" if args.user_approve else "cli",
            provider=args.provider,
            request_id=args.request_id,
            approval_token=args.approval_token,
            user_approved=args.user_approve,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
