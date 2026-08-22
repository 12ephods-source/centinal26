from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("tools/dedupe-organizer/verify_device_evidence.py")
DATA_FILES = {
    "device_profile.txt": "Android\nTermux\n",
    "self_test.txt": "PASS\n",
    "sqlite_integrity.txt": "PASS\n",
    "audit_verify.txt": "PASS\n",
    "storage_probe.txt": "PASS\n",
    "process_restart.txt": "PASS\n",
    "boot_probe.txt": "PASS\n",
}


def _write_bundle(root: Path, *, device_originated: bool = True) -> Path:
    bundle = root / "bundle"
    bundle.mkdir()
    acceptance = {
        "schema_version": "1.0",
        "project": "dedupe-organizer",
        "release": "2.1.0",
        "device_originated": device_originated,
        "android_detected": True,
        "termux_detected": True,
        "boot_id": "boot-test-id",
        "collected_at_utc": "2026-08-22T18:40:00Z",
        "tests": {
            "self_test": "PASS",
            "sqlite_integrity": "PASS",
            "audit_verify": "PASS",
            "storage_probe": "PASS",
            "process_restart": "PASS",
            "boot_probe": "PASS",
        },
    }
    (bundle / "acceptance.json").write_text(json.dumps(acceptance), encoding="utf-8")
    for name, content in DATA_FILES.items():
        (bundle / name).write_text(content, encoding="utf-8")
    manifest_lines = []
    for name in ["acceptance.json", *DATA_FILES]:
        digest = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
        manifest_lines.append(f"{digest}  {name}")
    (bundle / "SHA256SUMS.txt").write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8"
    )
    return bundle


def _run(bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(bundle)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_accepts_structurally_valid_device_bundle(tmp_path: Path) -> None:
    result = _run(_write_bundle(tmp_path))
    assert result.returncode == 0
    assert "PASS:" in result.stdout


def test_rejects_host_claim(tmp_path: Path) -> None:
    result = _run(_write_bundle(tmp_path, device_originated=False))
    assert result.returncode == 1
    assert "device_originated must equal True" in result.stdout


def test_rejects_tampered_evidence(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    (bundle / "self_test.txt").write_text("FAIL\n", encoding="utf-8")
    result = _run(bundle)
    assert result.returncode == 1
    assert "sha256 mismatch for self_test.txt" in result.stdout
