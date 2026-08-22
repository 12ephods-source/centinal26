from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REQUIRED_FILES = {
    "acceptance.json",
    "device_profile.txt",
    "self_test.txt",
    "sqlite_integrity.txt",
    "audit_verify.txt",
    "storage_probe.txt",
    "process_restart.txt",
    "boot_probe.txt",
    "SHA256SUMS.txt",
}

REQUIRED_TESTS = {
    "self_test",
    "sqlite_integrity",
    "audit_verify",
    "storage_probe",
    "process_restart",
    "boot_probe",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"malformed manifest line: {raw_line!r}")
        expected, name = parts
        entries[name.lstrip("*")] = expected.lower()
    return entries


def verify_bundle(bundle: Path) -> list[str]:
    errors: list[str] = []
    missing = sorted(name for name in REQUIRED_FILES if not (bundle / name).is_file())
    if missing:
        return [f"missing required file: {name}" for name in missing]

    try:
        record = json.loads((bundle / "acceptance.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid acceptance.json: {exc}"]

    expected_fields = {
        "schema_version": "1.0",
        "project": "dedupe-organizer",
        "release": "2.1.0",
        "device_originated": True,
        "android_detected": True,
        "termux_detected": True,
    }
    for key, expected in expected_fields.items():
        if record.get(key) != expected:
            errors.append(f"{key} must equal {expected!r}")

    for key in ("boot_id", "collected_at_utc"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            errors.append(f"{key} must be a non-empty string")

    tests = record.get("tests")
    if not isinstance(tests, dict):
        errors.append("tests must be an object")
    else:
        for test_name in sorted(REQUIRED_TESTS):
            if tests.get(test_name) != "PASS":
                errors.append(f"tests.{test_name} must equal 'PASS'")

    try:
        manifest = parse_manifest(bundle / "SHA256SUMS.txt")
    except (OSError, ValueError) as exc:
        errors.append(f"invalid SHA256SUMS.txt: {exc}")
        manifest = {}

    for name in sorted(REQUIRED_FILES - {"SHA256SUMS.txt"}):
        expected = manifest.get(name)
        if expected is None:
            errors.append(f"manifest missing {name}")
            continue
        actual = sha256(bundle / name)
        if actual != expected:
            errors.append(f"sha256 mismatch for {name}: {actual} != {expected}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()

    errors = verify_bundle(args.bundle)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print("PASS: authentic-device evidence contract satisfied structurally")
    print("LIMITATION: structural validation does not prove hardware-key identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
