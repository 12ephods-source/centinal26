from __future__ import annotations

import hashlib
import json
import os
import platform
import sqlite3
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from .core import AuditLog, Engine, Grant, JobStore, Verification

EVIDENCE_FILES = {"audit.jsonl", "qualification.json", "queue.sqlite3"}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_qualification_echo(
    data: dict[str, Any], output: dict[str, Any]
) -> Verification:
    expected = {"received": data}
    return Verification(
        passed=output == expected,
        evidence={"expected": expected, "observed": output},
    )


def platform_identity() -> dict[str, Any]:
    termux_prefix = os.environ.get("PREFIX", "")
    is_termux = "com.termux" in termux_prefix
    is_android = bool(os.environ.get("ANDROID_ROOT")) or is_termux
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "termux": is_termux,
        "android": is_android,
        "physical_device_inferred": is_termux and is_android,
    }


def run_qualification(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    audit = AuditLog(output_dir / "audit.jsonl")
    store = JobStore(output_dir / "queue.sqlite3")
    runtime = Engine(store, audit)
    runtime.register(
        "qualification.echo",
        lambda data: {"received": data},
        _verify_qualification_echo,
    )
    grant = Grant(
        grant_id=str(uuid.uuid4()),
        capability="qualification.echo",
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )
    job_id = runtime.submit("qualification.echo", {"probe": "centinal26"}, grant)
    completed_id = runtime.run_once()
    identity = platform_identity()
    report = {
        "schema_version": 1,
        "qualification_id": str(uuid.uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "platform": identity,
        "checks": {
            "job_completed": completed_id == job_id,
            "job_verified": store.counts() == {"verified": 1},
            "audit_chain_valid": audit.verify(),
        },
        "validation_scope": "PHYSICAL_ANDROID" if identity["physical_device_inferred"] else "HOST_ONLY",
    }
    report["passed"] = all(report["checks"].values())
    _write_json(output_dir / "qualification.json", report)
    manifest = {
        "schema_version": 1,
        "files": {name: _sha256(output_dir / name) for name in sorted(EVIDENCE_FILES)},
    }
    _write_json(output_dir / "manifest.json", manifest)
    return report


def _safe_manifest_files(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict) or set(value) != EVIDENCE_FILES:
        return None
    for name, digest in value.items():
        path = PurePosixPath(name)
        if path.is_absolute() or len(path.parts) != 1 or ".." in path.parts:
            return None
        if not isinstance(digest, str) or len(digest) != 64:
            return None
        try:
            int(digest, 16)
        except ValueError:
            return None
    return value


def assess_bundle(output_dir: Path) -> dict[str, Any]:
    checks = {
        "manifest_valid": False,
        "hashes_valid": False,
        "qualification_valid": False,
        "audit_chain_valid": False,
        "queue_state_valid": False,
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "bundle": str(output_dir),
        "checks": checks,
        "validation_scope": None,
        "decision": "INVALID",
        "release_review_eligible": False,
        "automatic_promotion": False,
    }
    try:
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            return report
        files = _safe_manifest_files(manifest.get("files"))
        if files is None:
            return report
        checks["manifest_valid"] = True
        checks["hashes_valid"] = all(
            (output_dir / name).is_file() and _sha256(output_dir / name) == digest
            for name, digest in files.items()
        )
        if not checks["hashes_valid"]:
            return report
        qualification = json.loads((output_dir / "qualification.json").read_text(encoding="utf-8"))
        scope = qualification.get("validation_scope")
        checks["qualification_valid"] = (
            qualification.get("schema_version") == 1
            and qualification.get("passed") is True
            and scope in {"HOST_ONLY", "PHYSICAL_ANDROID"}
            and all(qualification.get("checks", {}).values())
        )
        report["validation_scope"] = scope
        checks["audit_chain_valid"] = AuditLog(output_dir / "audit.jsonl").verify()
        connection = sqlite3.connect(f"file:{output_dir / 'queue.sqlite3'}?mode=ro", uri=True)
        row = connection.execute(
            "SELECT COUNT(*), SUM(CASE WHEN state='verified' THEN 1 ELSE 0 END) FROM jobs"
        ).fetchone()
        connection.close()
        checks["queue_state_valid"] = row == (1, 1)
    except (OSError, KeyError, TypeError, ValueError, sqlite3.Error, json.JSONDecodeError):
        return report
    if not all(checks.values()):
        return report
    if report["validation_scope"] == "PHYSICAL_ANDROID":
        report["decision"] = "REVIEW"
        report["release_review_eligible"] = True
    else:
        report["decision"] = "HOST_VALIDATED"
    return report


def verify_bundle(output_dir: Path) -> bool:
    return assess_bundle(output_dir)["decision"] != "INVALID"
