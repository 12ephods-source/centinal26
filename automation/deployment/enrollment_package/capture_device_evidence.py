"""Capture device-originated Automation OS enrollment evidence.

Designed to run inside Termux on Android. Non-Android execution can exercise
this collector but can never produce a physical-device PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def run_command(command: list[str], timeout: int = 20) -> dict[str, Any]:
    if shutil.which(command[0]) is None:
        return {"command": command, "available": False, "returncode": None, "stdout": "", "stderr": "command unavailable"}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return {"command": command, "available": True, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"command": command, "available": True, "returncode": None, "stdout": exc.stdout or "", "stderr": "timeout"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_optional(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def normalize_commit(value: str | None) -> str | None:
    candidate = (value or "").strip().lower()
    return candidate if re.fullmatch(r"[0-9a-f]{40}", candidate) else None


def detect_android() -> dict[str, Any]:
    prefix = os.environ.get("PREFIX", "")
    signals = {
        "ANDROID_ROOT": os.environ.get("ANDROID_ROOT"),
        "ANDROID_DATA": os.environ.get("ANDROID_DATA"),
        "PREFIX": prefix,
        "system_build_prop": Path("/system/build.prop").exists(),
        "termux_prefix": "com.termux" in prefix,
    }
    is_android = bool(signals["ANDROID_ROOT"] or signals["system_build_prop"] or signals["termux_prefix"])
    return {"is_android": is_android, "signals": signals}


def collect(device_id: str, source_commit: str | None = None) -> dict[str, Any]:
    android = detect_android()
    commands = {
        "uname": run_command(["uname", "-a"]),
        "getprop": run_command(["getprop"]),
        "termux_info": run_command(["termux-info"]),
        "termux_packages": run_command(["pkg", "list-installed"]),
        "android_packages_pm": run_command(["pm", "list", "packages"]),
        "android_packages_cmd": run_command(["cmd", "package", "list", "packages"]),
        "git_head": run_command(["git", "rev-parse", "HEAD"]),
    }
    package_sources = [
        key
        for key in ("android_packages_pm", "android_packages_cmd")
        if commands[key]["available"]
        and commands[key]["returncode"] == 0
        and commands[key]["stdout"].strip()
    ]
    observed_commit = normalize_commit(source_commit)
    if observed_commit is None and commands["git_head"]["returncode"] == 0:
        observed_commit = normalize_commit(commands["git_head"]["stdout"])
    return {
        "schema_version": "1.1",
        "captured_at_utc": utc_now(),
        "device_id": device_id,
        "status": "DEVICE_EVIDENCE_CAPTURED" if android["is_android"] else "HOST_ONLY_NOT_DEVICE_EVIDENCE",
        "physical_device_gate": "EVIDENCE_CAPTURED_UNVERIFIED" if android["is_android"] else "NOT_APPLICABLE_HOST",
        "software_provenance": {
            "repository": "12ephods-source/centinal26",
            "source_commit": observed_commit,
            "status": "OBSERVED" if observed_commit else "MISSING",
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "android_detection": android,
            "boot_id": read_optional("/proc/sys/kernel/random/boot_id"),
        },
        "package_inventory_sources": package_sources,
        "commands": commands,
        "claims": {
            "device_origin": "OBSERVED" if android["is_android"] else "FAILED",
            "integrity": "UNVERIFIED_UNTIL_MANIFEST_CHECK",
            "software_provenance": "OBSERVED" if observed_commit else "MISSING",
            "enrollment": "PENDING_CONTROLLER_VERIFICATION",
            "worker_activation": "PENDING_CONTROLLER_VERIFICATION",
        },
    }


def write_bundle(output_dir: Path, evidence: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "device_evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    summary = {
        "device_id": evidence["device_id"],
        "captured_at_utc": evidence["captured_at_utc"],
        "status": evidence["status"],
        "physical_device_gate": evidence["physical_device_gate"],
        "source_commit": evidence.get("software_provenance", {}).get("source_commit"),
        "package_inventory_sources": evidence["package_inventory_sources"],
    }
    (output_dir / "validation_report.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {"schema_version": "1.0", "generated_at_utc": utc_now(), "files": {}}
    for path in sorted(output_dir.iterdir()):
        if path.name != "MANIFEST.sha256.json":
            manifest["files"][path.name] = sha256_file(path)
    (output_dir / "MANIFEST.sha256.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", default=platform.node() or "UNKNOWN_DEVICE")
    parser.add_argument("--source-commit")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    evidence = collect(args.device_id, source_commit=args.source_commit)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output or f"guardian_physical_validation_{stamp}")
    write_bundle(output, evidence)
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "output": str(output),
                "physical_device_gate": evidence["physical_device_gate"],
                "source_commit": evidence["software_provenance"]["source_commit"],
            },
            indent=2,
        )
    )
    return 0 if evidence["status"] == "DEVICE_EVIDENCE_CAPTURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
