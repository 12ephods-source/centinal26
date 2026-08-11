from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Grant:
    grant_id: str
    capability: str
    expires_at: str

    def permits(self, capability: str) -> bool:
        return self.capability == capability and datetime.fromisoformat(
            self.expires_at
        ) > datetime.now(UTC)


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = "0" * 64
        if self.path.exists():
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if lines:
                previous = json.loads(lines[-1])["hash"]
        record = {
            "timestamp": now_iso(),
            "event": event,
            "payload": payload,
            "previous_hash": previous,
        }
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
        record["hash"] = hashlib.sha256(canonical.encode()).hexdigest()
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def verify(self) -> bool:
        previous = "0" * 64
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            found = record.pop("hash")
            if record["previous_hash"] != previous:
                return False
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
            if hashlib.sha256(canonical.encode()).hexdigest() != found:
                return False
            previous = found
        return True


class JobStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, capability TEXT NOT NULL, input TEXT NOT NULL,
                grant TEXT NOT NULL, state TEXT NOT NULL, result TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    def submit(self, capability: str, data: dict[str, Any], grant: Grant) -> str:
        job_id = str(uuid.uuid4())
        timestamp = now_iso()
        self.connection.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, 'queued', NULL, ?, ?)",
            (job_id, capability, json.dumps(data), json.dumps(asdict(grant)), timestamp, timestamp),
        )
        self.connection.commit()
        return job_id

    def next_job(self) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1"
        ).fetchone()

    def transition(self, job_id: str, state: str, result: dict[str, Any]) -> None:
        self.connection.execute(
            "UPDATE jobs SET state=?, result=?, updated_at=? WHERE id=?",
            (state, json.dumps(result), now_iso(), job_id),
        )
        self.connection.commit()

    def counts(self) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT state, COUNT(*) AS count FROM jobs GROUP BY state"
        ).fetchall()
        return {row["state"]: row["count"] for row in rows}


Capability = Callable[[dict[str, Any]], dict[str, Any]]


class Engine:
    def __init__(self, store: JobStore, audit: AuditLog):
        self.store = store
        self.audit = audit
        self.capabilities: dict[str, Capability] = {}

    def register(self, name: str, function: Capability) -> None:
        self.capabilities[name] = function

    def submit(self, capability: str, data: dict[str, Any], grant: Grant) -> str:
        if not grant.permits(capability):
            self.audit.append("authorization_denied", {"capability": capability})
            raise PermissionError("grant does not authorize this capability")
        if capability not in self.capabilities:
            raise KeyError(f"unknown capability: {capability}")
        job_id = self.store.submit(capability, data, grant)
        self.audit.append("job_queued", {"job_id": job_id, "capability": capability})
        return job_id

    def run_once(self) -> str | None:
        row = self.store.next_job()
        if row is None:
            return None
        job_id = row["id"]
        grant = Grant(**json.loads(row["grant"]))
        capability = row["capability"]
        if not grant.permits(capability):
            result = {"error": "authorization expired or mismatched"}
            self.store.transition(job_id, "rejected", result)
            self.audit.append("job_rejected", {"job_id": job_id, **result})
            return job_id
        self.audit.append("job_started", {"job_id": job_id, "capability": capability})
        try:
            output = self.capabilities[capability](json.loads(row["input"]))
            result = {"ok": True, "output": output}
            state = "verified"
        except Exception as error:  # noqa: BLE001 - capability boundary records failures
            result = {"ok": False, "error": type(error).__name__, "message": str(error)}
            state = "failed"
        self.store.transition(job_id, state, result)
        self.audit.append(f"job_{state}", {"job_id": job_id, **result})
        return job_id
