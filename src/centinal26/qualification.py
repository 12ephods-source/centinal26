from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .core import AuditLog, Engine, Grant, JobStore


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def platform_identity() -> dict[str, Any]:
    termux_prefix = os.environ.get("PREFIX", "")
    is_termux = "com.termux" in termux_prefix
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "termux": is_termux,
        "android": bool(os.environ.get("ANDROID_ROOT")) or is_termux,
    }


def run_qualification(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    audit = AuditLog(output_dir / "audit.jsonl")
    store = JobStore(output_dir / "queue.sqlite3")
    runtime = Engine(store, audit)
    runtime.register("qualification.echo", lambda data: {"received": data})
    grant = Grant(
        grant_id=str(uuid.uuid4()),
        capability="qualification.echo",
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )
    job_id = runtime.submit("qualification.echo", {"probe": "centinal26"}, grant)
    completed_id = runtime.run_once()
    report = {
        "schema_version": 1,
        "qualification_id": str(uuid.uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "platform": platform_identity(),
        "checks": {
            "job_completed": completed_id == job_id,
            "job_verified": store.counts() == {"verified": 1},
            "audit_chain_valid": audit.verify(),
        },
        "validation_scope": "PHYSICAL_ANDROID" if platform_identity()["android"] else "HOST_ONLY",
    }
    report["passed"] = all(report["checks"].values())
    _write_json(output_dir / "qualification.json", report)
    evidence_files = ["audit.jsonl", "qualification.json", "queue.sqlite3"]
    manifest = {
        "schema_version": 1,
        "files": {name: _sha256(output_dir / name) for name in evidence_files},
    }
    _write_json(output_dir / "manifest.json", manifest)
    return report


def verify_bundle(output_dir: Path) -> bool:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest["files"]
        return bool(files) and all(
            (output_dir / name).is_file() and _sha256(output_dir / name) == expected
            for name, expected in files.items()
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
