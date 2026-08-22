#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PACKAGE_RE = re.compile(r"^package:(?P<path>.*?)=(?P<package>[^ ]+)(?:\s+installer=(?P<installer>.*?))?(?:\s+uid:(?P<uid>\d+))?(?:\s+versionCode:(?P<version_code>\d+))?$")


def _run_fixed(argv: list[str]) -> str:
    proc = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed rc={proc.returncode}: {' '.join(argv)}: {proc.stderr[:500]}")
    return proc.stdout


def parse_package_lines(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("package:"):
            continue
        match = PACKAGE_RE.match(line)
        if match:
            item: dict[str, Any] = {
                "package": match.group("package"),
                "source_path": match.group("path") or None,
                "installer": (match.group("installer") or "").strip() or None,
                "uid": int(match.group("uid")) if match.group("uid") else None,
                "version_code": int(match.group("version_code")) if match.group("version_code") else None,
            }
        else:
            body = line[len("package:"):]
            if "=" in body:
                path, package = body.split("=", 1)
            else:
                path, package = None, body
            item = {"package": package.split()[0], "source_path": path, "installer": None, "uid": None, "version_code": None}
        rows.append(item)
    dedup = {row["package"]: row for row in rows if row.get("package")}
    return [dedup[name] for name in sorted(dedup)]


def collect() -> dict[str, Any]:
    attempts = [
        ["/system/bin/cmd", "package", "list", "packages", "-f", "-i", "-U", "--show-versioncode"],
        ["/system/bin/pm", "list", "packages", "-f", "-i", "-U", "--show-versioncode"],
        ["/system/bin/pm", "list", "packages", "-f"],
    ]
    last_error = None
    output = None
    method = None
    for argv in attempts:
        try:
            output = _run_fixed(argv)
            method = " ".join(argv)
            break
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            last_error = str(exc)
    if output is None:
        raise RuntimeError(last_error or "no Android package-manager command available")

    packages = parse_package_lines(output)
    boot_id_path = Path("/proc/sys/kernel/random/boot_id")
    boot_id = boot_id_path.read_text(encoding="utf-8").strip() if boot_id_path.exists() else None
    payload = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "fleet_device_id": os.environ.get("CENTINAL26_FLEET_DEVICE_ID"),
        "worker_instance_id": os.environ.get("CENTINAL26_WORKER_INSTANCE_ID"),
        "boot_id": boot_id,
        "collection_method": method,
        "package_visibility_note": "Android package visibility may limit what a non-privileged Termux process can enumerate; absence from this list is not proof of absence from the device.",
        "package_count": len(packages),
        "packages": packages,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload["inventory_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Centinal26 Android installed-app inventory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = collect()
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
