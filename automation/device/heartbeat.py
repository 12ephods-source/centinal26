"""Device worker heartbeat evidence.

Designed for an already verified Android/Termux worker. The heartbeat carries
identity and boot-binding metadata but does not itself establish enrollment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_optional(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def is_android_termux() -> bool:
    prefix = os.environ.get("PREFIX", "")
    return bool(os.environ.get("ANDROID_ROOT") or "com.termux" in prefix or Path("/system/build.prop").exists())


def create_heartbeat(device_id: str, enrollment_digest: str, sequence: int = 1) -> dict:
    android = is_android_termux()
    heartbeat = {
        "schema_version": "1.0",
        "device_id": device_id,
        "sequence": sequence,
        "timestamp": utc_now(),
        "boot_id": read_optional("/proc/sys/kernel/random/boot_id"),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "android_termux_signal": android,
        },
        "enrollment_digest": enrollment_digest,
        "status": "ONLINE_OBSERVED" if android else "HOST_ONLY_NOT_DEVICE_HEARTBEAT",
        "verification_status": "PENDING_CONTROLLER_VERIFICATION",
    }
    canonical = json.dumps(heartbeat, sort_keys=True, separators=(",", ":")).encode()
    heartbeat["record_sha256"] = hashlib.sha256(canonical).hexdigest()
    return heartbeat


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--enrollment-digest", required=True)
    parser.add_argument("--sequence", type=int, default=1)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    heartbeat = create_heartbeat(args.device_id, args.enrollment_digest, args.sequence)
    Path(args.output).write_text(json.dumps(heartbeat, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": heartbeat["status"], "output": args.output}, indent=2))
    return 0 if heartbeat["status"] == "ONLINE_OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
