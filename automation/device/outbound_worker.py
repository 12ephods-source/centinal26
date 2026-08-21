"""Outbound HTTPS control loop for commissioned Android/Termux workers.

The controller never gains an arbitrary shell. Jobs are HMAC-authenticated,
targeted, expiring capability invocations. The worker supports a closed set of
local diagnostic capabilities and records an append-only hash-chained journal.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALLOWED_CAPABILITIES = frozenset({"diagnostic_status", "inventory_snapshot"})
JOB_FIELDS = frozenset(
    {
        "task_id",
        "target_device_id",
        "capability",
        "parameters",
        "authorization_scope",
        "expires_at",
        "nonce",
        "expected_source_commit",
        "signature",
    }
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_bytes(value: dict[str, Any], *, omit: frozenset[str] = frozenset()) -> bytes:
    filtered = {key: item for key, item in value.items() if key not in omit}
    return json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode()


def sign_record(record: dict[str, Any], secret: bytes) -> str:
    return hmac.new(secret, canonical_bytes(record, omit=frozenset({"signature"})), hashlib.sha256).hexdigest()


def verify_signature(record: dict[str, Any], secret: bytes) -> bool:
    supplied = record.get("signature")
    return isinstance(supplied, str) and hmac.compare_digest(supplied, sign_record(record, secret))


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class WorkerConfig:
    device_id: str
    source_commit: str
    queue_url: str
    result_url: str
    credential_path: Path
    state_dir: Path
    poll_seconds: int = 30
    max_backoff_seconds: int = 600

    @classmethod
    def from_json(cls, path: Path) -> "WorkerConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            device_id=raw["device_id"],
            source_commit=raw["source_commit"],
            queue_url=raw["queue_url"],
            result_url=raw["result_url"],
            credential_path=Path(raw["credential_path"]).expanduser(),
            state_dir=Path(raw["state_dir"]).expanduser(),
            poll_seconds=int(raw.get("poll_seconds", 30)),
            max_backoff_seconds=int(raw.get("max_backoff_seconds", 600)),
        )


class Journal:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def tail_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        last = ""
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        if not last:
            return "0" * 64
        record = json.loads(last)
        return record["record_hash"]

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        record = {
            "timestamp": utc_now().isoformat(),
            "previous_hash": self.tail_hash(),
            **event,
        }
        record["record_hash"] = hashlib.sha256(canonical_bytes(record)).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return record


class Worker:
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        self.secret = self._load_secret()
        self.journal = Journal(self.config.state_dir / "journal.jsonl")
        self.nonce_path = self.config.state_dir / "seen_nonces.json"

    def _load_secret(self) -> bytes:
        stat = self.config.credential_path.stat()
        if stat.st_mode & 0o077:
            raise PermissionError("worker credential must not be group/world accessible")
        secret = self.config.credential_path.read_bytes().strip()
        if len(secret) < 32:
            raise ValueError("worker credential must contain at least 32 bytes")
        return secret

    def _seen_nonces(self) -> set[str]:
        if not self.nonce_path.exists():
            return set()
        value = json.loads(self.nonce_path.read_text(encoding="utf-8"))
        return set(value if isinstance(value, list) else [])

    def _remember_nonce(self, nonce: str) -> None:
        seen = sorted(self._seen_nonces() | {nonce})[-4096:]
        temp = self.nonce_path.with_suffix(".tmp")
        temp.write_text(json.dumps(seen), encoding="utf-8")
        temp.replace(self.nonce_path)

    def validate_job(self, job: Any, *, now: datetime | None = None) -> list[str]:
        errors: list[str] = []
        now = now or utc_now()
        if not isinstance(job, dict):
            return ["JOB_OBJECT_REQUIRED"]
        if frozenset(job) != JOB_FIELDS:
            errors.append("JOB_FIELDS_INVALID")
        if job.get("target_device_id") != self.config.device_id:
            errors.append("DEVICE_TARGET_MISMATCH")
        capability = job.get("capability")
        if capability not in ALLOWED_CAPABILITIES:
            errors.append("CAPABILITY_NOT_ALLOWED")
        if job.get("expected_source_commit") != self.config.source_commit:
            errors.append("SOURCE_COMMIT_MISMATCH")
        if job.get("authorization_scope") != {"device_id": self.config.device_id, "capability": capability}:
            errors.append("AUTHORIZATION_SCOPE_MISMATCH")
        nonce = job.get("nonce")
        if not isinstance(nonce, str) or not nonce:
            errors.append("NONCE_INVALID")
        elif nonce in self._seen_nonces():
            errors.append("NONCE_REPLAY")
        try:
            if parse_time(job["expires_at"]) <= now:
                errors.append("JOB_EXPIRED")
        except (KeyError, TypeError, ValueError):
            errors.append("EXPIRY_INVALID")
        if not verify_signature(job, self.secret):
            errors.append("SIGNATURE_INVALID")
        if not isinstance(job.get("parameters"), dict):
            errors.append("PARAMETERS_INVALID")
        if not isinstance(job.get("task_id"), str) or not job.get("task_id"):
            errors.append("TASK_ID_INVALID")
        return errors

    def execute_job(self, job: dict[str, Any]) -> dict[str, Any]:
        errors = self.validate_job(job)
        if errors:
            result = {"task_id": job.get("task_id"), "status": "REJECTED", "errors": errors}
            self.journal.append({"event": "job_rejected", "result": result})
            return result

        nonce = job["nonce"]
        self._remember_nonce(nonce)
        capability = job["capability"]
        if capability == "diagnostic_status":
            output = {
                "platform": platform.platform(),
                "machine": platform.machine(),
                "boot_id": _read_optional(Path("/proc/sys/kernel/random/boot_id")),
                "android_termux": bool(os.environ.get("ANDROID_ROOT") or "com.termux" in os.environ.get("PREFIX", "")),
                "source_commit": self.config.source_commit,
            }
        elif capability == "inventory_snapshot":
            output = {
                "android_release": _run_getprop("ro.build.version.release"),
                "manufacturer": _run_getprop("ro.product.manufacturer"),
                "model": _run_getprop("ro.product.model"),
                "termux_prefix": os.environ.get("PREFIX"),
            }
        else:  # pragma: no cover - protected by validation
            raise AssertionError("unreachable capability")

        result: dict[str, Any] = {
            "task_id": job["task_id"],
            "device_id": self.config.device_id,
            "capability": capability,
            "status": "PASS",
            "timestamp": utc_now().isoformat(),
            "source_commit": self.config.source_commit,
            "output": output,
            "previous_evidence_hash": self.journal.tail_hash(),
        }
        result["signature"] = sign_record(result, self.secret)
        self.journal.append({"event": "job_completed", "result": result})
        return result

    def _request_json(self, url: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
        data = None if body is None else canonical_bytes(body)
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Accept", "application/json")
        request.add_header("Content-Type", "application/json")
        request.add_header("X-Frost-Device", self.config.device_id)
        if body is not None:
            request.add_header("X-Frost-Signature", sign_record(body, self.secret))
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def poll_once(self) -> str:
        payload = self._request_json(f"{self.config.queue_url}?device_id={self.config.device_id}")
        job = payload.get("job") if isinstance(payload, dict) else None
        if job is None:
            self.journal.append({"event": "poll_empty"})
            return "EMPTY"
        result = self.execute_job(job)
        self._request_json(self.config.result_url, method="POST", body=result)
        self.journal.append({"event": "result_acknowledged", "task_id": result.get("task_id")})
        return result["status"]

    def run_forever(self) -> None:
        failures = 0
        while True:
            try:
                self.poll_once()
                failures = 0
                delay = self.config.poll_seconds
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                failures += 1
                self.journal.append({"event": "transport_error", "error": type(exc).__name__})
                cap = min(self.config.max_backoff_seconds, self.config.poll_seconds * (2 ** min(failures, 8)))
                delay = max(1, int(random.uniform(cap / 2, cap)))
            time.sleep(delay)


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _run_getprop(name: str) -> str | None:
    import subprocess

    try:
        completed = subprocess.run(
            ["getprop", name], capture_output=True, text=True, timeout=5, check=False
        )
    except OSError:
        return None
    value = completed.stdout.strip()
    return value or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    worker = Worker(WorkerConfig.from_json(args.config))
    if args.once:
        print(worker.poll_once())
    else:
        worker.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
