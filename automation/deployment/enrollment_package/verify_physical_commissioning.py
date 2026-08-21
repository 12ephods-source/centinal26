"""Verify one physical Android commissioning package end to end.

The package must contain enrollment evidence plus a heartbeat bound to the
SHA-256 of the verified enrollment manifest. A PASS here establishes
controller-side eligibility, not production success for arbitrary workloads.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from automation.deployment.enrollment_package.verify_device_evidence import verify_bundle
from automation.device.verify_worker_heartbeat import verify_heartbeat


def _safe_extract(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        for member in members:
            target = (destination / member.filename).resolve()
            if destination.resolve() not in target.parents and target != destination.resolve():
                raise ValueError("unsafe zip member path")
        archive.extractall(destination)
    roots = [path for path in destination.iterdir() if path.is_dir()]
    return roots[0] if len(roots) == 1 else destination


def verify_commissioning(root: Path, expected_source_commit: str | None = None) -> dict:
    enrollment = verify_bundle(root, expected_source_commit=expected_source_commit)
    result = {
        "status": "REJECTED",
        "enrollment": enrollment,
        "heartbeat": None,
        "worker_activation": "REJECTED",
        "errors": [],
    }
    if enrollment.get("enrollment") != "VERIFIED_ELIGIBLE":
        result["errors"].append("ENROLLMENT_NOT_ELIGIBLE")
        return result

    heartbeat_path = root / "worker_heartbeat.json"
    if not heartbeat_path.is_file():
        result["errors"].append("HEARTBEAT_MISSING")
        return result

    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    heartbeat_result = verify_heartbeat(
        heartbeat,
        expected_device_id=enrollment["device_id"],
        expected_enrollment_digest=enrollment["enrollment_digest"],
        expected_boot_id=enrollment["boot_id"],
    )
    result["heartbeat"] = heartbeat_result
    if not heartbeat_result["eligible"]:
        result["errors"].extend(heartbeat_result["errors"])
        return result

    result["status"] = "VERIFIED_PHYSICAL_COMMISSIONING_ELIGIBLE"
    result["worker_activation"] = "VERIFIED_ACTIVE_ELIGIBLE"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--expected-source-commit")
    args = parser.parse_args()

    if args.package.is_dir():
        result = verify_commissioning(args.package, args.expected_source_commit)
    else:
        with tempfile.TemporaryDirectory() as directory:
            root = _safe_extract(args.package, Path(directory))
            result = verify_commissioning(root, args.expected_source_commit)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VERIFIED_PHYSICAL_COMMISSIONING_ELIGIBLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
