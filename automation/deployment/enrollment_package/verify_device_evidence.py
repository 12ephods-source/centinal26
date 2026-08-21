"""Controller-side verification for Android/Termux enrollment evidence bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "device_evidence.json",
    "validation_report.json",
    "MANIFEST.sha256.json",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle(root: Path) -> dict[str, Any]:
    missing = sorted(name for name in REQUIRED_FILES if not (root / name).is_file())
    result: dict[str, Any] = {
        "bundle": str(root),
        "integrity": "FAILED",
        "device_origin": "UNVERIFIED",
        "inventory": "UNVERIFIED",
        "enrollment": "REJECTED",
        "worker_activation": "REJECTED",
        "errors": [],
    }
    if missing:
        result["errors"].append({"missing_files": missing})
        return result

    manifest = json.loads((root / "MANIFEST.sha256.json").read_text(encoding="utf-8"))
    for name in ("device_evidence.json", "validation_report.json"):
        expected = manifest.get("files", {}).get(name)
        actual = sha256_file(root / name)
        if not expected or expected != actual:
            result["errors"].append(
                {"file": name, "expected_sha256": expected, "actual_sha256": actual}
            )
    if result["errors"]:
        return result
    result["integrity"] = "VERIFIED"

    evidence = json.loads((root / "device_evidence.json").read_text(encoding="utf-8"))
    report = json.loads((root / "validation_report.json").read_text(encoding="utf-8"))
    android = evidence.get("platform", {}).get("android_detection", {})
    signals = android.get("signals", {})
    android_signal_count = sum(
        bool(value)
        for value in (
            signals.get("ANDROID_ROOT"),
            signals.get("ANDROID_DATA"),
            signals.get("system_build_prop"),
            signals.get("termux_prefix"),
        )
    )
    consistent = (
        evidence.get("status") == "DEVICE_EVIDENCE_CAPTURED"
        and evidence.get("physical_device_gate") == "EVIDENCE_CAPTURED_UNVERIFIED"
        and report.get("status") == evidence.get("status")
        and report.get("device_id") == evidence.get("device_id")
        and android.get("is_android") is True
        and android_signal_count >= 1
        and bool(evidence.get("platform", {}).get("boot_id"))
    )
    if not consistent:
        result["errors"].append("device-origin invariants failed")
        return result
    result["device_origin"] = "VERIFIED_ANDROID_SIGNAL_SET"

    package_sources = evidence.get("package_inventory_sources", [])
    if package_sources:
        result["inventory"] = "OBSERVED"
    else:
        result["inventory"] = "MISSING_ANDROID_PACKAGE_INVENTORY"
        result["errors"].append("no successful Android package inventory source")
        return result

    result["device_id"] = evidence.get("device_id")
    result["boot_id"] = evidence.get("platform", {}).get("boot_id")
    result["captured_at_utc"] = evidence.get("captured_at_utc")
    result["enrollment"] = "VERIFIED_ELIGIBLE"
    result["worker_activation"] = "ELIGIBLE_PENDING_HEARTBEAT"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_bundle(args.bundle)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["enrollment"] == "VERIFIED_ELIGIBLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
