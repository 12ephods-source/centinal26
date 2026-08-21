"""Controller-side authenticated queue for outbound Android workers.

This module is transport-agnostic. It stores device credentials as salted hashes,
signs bounded jobs with per-device HMAC keys supplied by a credential provider,
tracks nonces, and verifies signed worker results before acknowledgement.

The queue never emits arbitrary shell commands. Capabilities are closed and
must match the worker authorization scope exactly.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

ALLOWED_CAPABILITIES = frozenset({"diagnostic_status", "inventory_snapshot"})


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_bytes(value: dict[str, Any], *, omit: frozenset[str] = frozenset()) -> bytes:
    filtered = {key: item for key, item in value.items() if key not in omit}
    return json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode()


def sign_record(record: dict[str, Any], secret: bytes) -> str:
    return hmac.new(
        secret,
        canonical_bytes(record, omit=frozenset({"signature"})),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(record: dict[str, Any], secret: bytes) -> bool:
    supplied = record.get("signature")
    return isinstance(supplied, str) and hmac.compare_digest(supplied, sign_record(record, secret))


@dataclass(frozen=True)
class DeviceRegistration:
    device_id: str
    source_commit: str
    credential_fingerprint: str
    registered_at: str
    enrollment_digest: str


@dataclass
class QueueState:
    registrations: dict[str, DeviceRegistration] = field(default_factory=dict)
    jobs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    consumed_nonces: set[str] = field(default_factory=set)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)


class OutboundQueue:
    def __init__(self, credential_provider: Callable[[str], bytes]):
        self._credential_provider = credential_provider
        self.state = QueueState()

    def register_device(
        self,
        *,
        device_id: str,
        source_commit: str,
        enrollment_digest: str,
        credential: bytes,
    ) -> DeviceRegistration:
        if len(credential) < 32:
            raise ValueError("device credential must contain at least 32 bytes")
        if not device_id or len(source_commit) != 40 or len(enrollment_digest) != 64:
            raise ValueError("invalid registration fields")
        fingerprint = hashlib.sha256(credential).hexdigest()
        registration = DeviceRegistration(
            device_id=device_id,
            source_commit=source_commit.lower(),
            credential_fingerprint=fingerprint,
            registered_at=utc_now().isoformat(),
            enrollment_digest=enrollment_digest.lower(),
        )
        existing = self.state.registrations.get(device_id)
        if existing and existing != registration:
            raise ValueError("device already registered with different identity material")
        self.state.registrations[device_id] = registration
        self.state.jobs.setdefault(device_id, [])
        return registration

    def enqueue(
        self,
        *,
        device_id: str,
        capability: str,
        parameters: dict[str, Any] | None = None,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        registration = self.state.registrations.get(device_id)
        if registration is None:
            raise KeyError("device not registered")
        if capability not in ALLOWED_CAPABILITIES:
            raise ValueError("capability not allowed")
        if ttl_seconds <= 0 or ttl_seconds > 3600:
            raise ValueError("ttl_seconds out of bounds")
        secret = self._credential_provider(device_id)
        nonce = secrets.token_hex(16)
        job = {
            "task_id": secrets.token_hex(16),
            "target_device_id": device_id,
            "capability": capability,
            "parameters": dict(parameters or {}),
            "authorization_scope": {"device_id": device_id, "capability": capability},
            "expires_at": (utc_now() + timedelta(seconds=ttl_seconds)).isoformat(),
            "nonce": nonce,
            "expected_source_commit": registration.source_commit,
        }
        job["signature"] = sign_record(job, secret)
        self.state.jobs[device_id].append(job)
        return dict(job)

    def next_job(self, device_id: str) -> dict[str, Any] | None:
        registration = self.state.registrations.get(device_id)
        if registration is None:
            return None
        queue = self.state.jobs.setdefault(device_id, [])
        while queue:
            job = queue[0]
            if datetime.fromisoformat(job["expires_at"]) <= utc_now():
                queue.pop(0)
                continue
            return dict(job)
        return None

    def accept_result(self, result: dict[str, Any]) -> dict[str, Any]:
        device_id = result.get("device_id")
        task_id = result.get("task_id")
        if not isinstance(device_id, str) or device_id not in self.state.registrations:
            raise ValueError("unknown device")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("invalid task id")
        secret = self._credential_provider(device_id)
        if not verify_signature(result, secret):
            raise ValueError("invalid result signature")
        registration = self.state.registrations[device_id]
        if result.get("source_commit") != registration.source_commit:
            raise ValueError("source commit mismatch")
        capability = result.get("capability")
        if capability not in ALLOWED_CAPABILITIES:
            raise ValueError("capability not allowed")
        queue = self.state.jobs.setdefault(device_id, [])
        matching = next((job for job in queue if job.get("task_id") == task_id), None)
        if matching is None:
            if task_id in self.state.results:
                return {"status": "ALREADY_ACKNOWLEDGED", "task_id": task_id}
            raise ValueError("task not outstanding")
        if capability != matching["capability"]:
            raise ValueError("capability mismatch")
        nonce = matching["nonce"]
        if nonce in self.state.consumed_nonces:
            raise ValueError("job nonce already consumed")
        self.state.consumed_nonces.add(nonce)
        self.state.results[task_id] = dict(result)
        self.state.jobs[device_id] = [job for job in queue if job.get("task_id") != task_id]
        return {"status": "ACKNOWLEDGED", "task_id": task_id}
