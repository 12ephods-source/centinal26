"""Controller-side verification for Android/Termux enrollment evidence bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "device_evidence.json",
    "validation_report.json",
    "MANIFEST.sha256.json",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_commit(value: str | None) -> str | None:
    candidate = (value or "").strip().lower()
    return candidate if re.fullmatch(r"[0-9a-f]{40}", candidate) else None


def verify_bundle(root: Path, expected_source_commit: str | None = None) -> dict[str, Any]:
    missing = sorted(name for name in REQUIRED_FILES if not (root / name).is_file())
    result: dict[str, Any] = {
        "bundle": str(root),
        "integrity": "FAILED",
        "software_provenance": "UNVERIFIED",
        "device_origin": "UNVERIFIED",
        "device_profile": None,
        "inventory": "UNVERIFIED",
        "enrollment": "REJECTED",
        "worker_activation": "REJECTED",
        "errors": [],
    }
    if missing:
        result["errors"].append({"missing_files": missing})
        return result

    manifest_path = root / "MANIFEST.sha256.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_digest = sha256_file(manifest_path)
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

    source_commit = normalize_commit(
        evidence.get("software_provenance", {}).get("source_commit")
    )
    report_commit = normalize_commit(report.get("source_commit"))
    expected_commit = normalize_commit(expected_source_commit)
    if source_commit is None or report_commit != source_commit:
        result["errors"].append("software source commit provenance missing or inconsistent")
        return result
    if expected_source_commit is not None and expected_commit is None:
        result["errors"].append("invalid expected source commit")
        return result
    if expected_commit is not None and source_commit != expected_commit:
        result["errors"].append(
            {
                "source_commit_mismatch": {
                    "expected": expected_commit,
                    "observed": source_commit,
                }
            }
        )
        return result
    result["source_commit"] = source_commit
    result["software_provenance"] = (
        "VERIFIED_EXPECTED_COMMIT" if expected_commit else "VERIFIED_PRESENT"
    )

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

    device_profile = evidence.get("device_profile")
    if not isinstance(device_profile, dict) or report.get("device_profile") != device_profile:
        result["errors"].append("device profile missing or inconsistent")
        return result
    result["device_profile"] = device_profile

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
    result["enrollment_digest"] = manifest_digest
    result["enrollment"] = "VERIFIED_ELIGIBLE"
    result["worker_activation"] = "ELIGIBLE_PENDING_HEARTBEAT"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--expected-source-commit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_bundle(
        args.bundle,
        expected_source_commit=args.expected_source_commit,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["enrollment"] == "VERIFIED_ELIGIBLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
