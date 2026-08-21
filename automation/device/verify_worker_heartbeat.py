"""Controller-side verification for an enrolled worker heartbeat."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ONLINE_WINDOW_SECONDS = 300


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def canonical_record_sha256(record: dict) -> str:
    payload = {key: value for key, value in record.items() if key != "record_sha256"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def verify_heartbeat(
    heartbeat: dict,
    *,
    expected_device_id: str,
    expected_enrollment_digest: str,
    expected_boot_id: str,
    now: datetime | None = None,
) -> dict:
    errors: list[str] = []
    now = now or datetime.now(UTC)

    if heartbeat.get("device_id") != expected_device_id:
        errors.append("DEVICE_ID_MISMATCH")
    if heartbeat.get("enrollment_digest") != expected_enrollment_digest:
        errors.append("ENROLLMENT_DIGEST_MISMATCH")
    if heartbeat.get("boot_id") != expected_boot_id or not expected_boot_id:
        errors.append("BOOT_ID_MISMATCH")
    if not heartbeat.get("platform", {}).get("android_termux_signal"):
        errors.append("ANDROID_TERMUX_SIGNAL_MISSING")
    if heartbeat.get("status") != "ONLINE_OBSERVED":
        errors.append("HEARTBEAT_STATUS_NOT_ONLINE")
    if heartbeat.get("record_sha256") != canonical_record_sha256(heartbeat):
        errors.append("RECORD_HASH_MISMATCH")

    try:
        timestamp = parse_time(heartbeat["timestamp"])
        age_seconds = (now - timestamp).total_seconds()
        if age_seconds < -30:
            errors.append("HEARTBEAT_FROM_FUTURE")
        elif age_seconds > ONLINE_WINDOW_SECONDS:
            errors.append("HEARTBEAT_STALE")
    except (KeyError, TypeError, ValueError):
        age_seconds = None
        errors.append("INVALID_TIMESTAMP")

    eligible = not errors
    return {
        "verified_at": now.isoformat(),
        "device_id": heartbeat.get("device_id"),
        "eligible": eligible,
        "worker_activation": "VERIFIED_ACTIVE_ELIGIBLE" if eligible else "REJECTED",
        "heartbeat_age_seconds": age_seconds,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("heartbeat")
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--enrollment-digest", required=True)
    parser.add_argument("--boot-id", required=True)
    args = parser.parse_args()
    heartbeat = json.loads(Path(args.heartbeat).read_text(encoding="utf-8"))
    result = verify_heartbeat(
        heartbeat,
        expected_device_id=args.device_id,
        expected_enrollment_digest=args.enrollment_digest,
        expected_boot_id=args.boot_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
