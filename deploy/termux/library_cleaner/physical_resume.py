"""Resume Centinal26's canonical Android physical gate when running in Termux.

This operator deliberately handles only the device-local half of physical
commissioning. It reads the qualified source revision from canonical GitHub
state, runs that exact pinned one-paste enrollment script once, and preserves
the returned ZIP. It never marks DEVICE_VALIDATED: controller verification,
worker observation, bounded work, and independent evidence remain separate.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

APP = Path.home() / ".local" / "share" / "frost-library-cleaner"
REPO = os.environ.get("CENTINAL26_REPO", "12ephods-source/centinal26")
PROJECT_STATE_PATH = "automation/PROJECT_STATE.json"
ENROLL_PATH = "automation/deployment/enrollment_package/termux_enroll_onepaste.sh"


def run(args: list[str], *, timeout: int = 900, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def gh_json(path: str) -> dict[str, Any]:
    result = run(["gh", "api", path], timeout=60)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "gh api failed").strip())
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise TypeError("GitHub API response must be an object")
    return value


def github_text(repo_path: str, ref: str = "main") -> str:
    payload = gh_json(f"repos/{REPO}/contents/{repo_path}?ref={ref}")
    content = payload.get("content")
    if not isinstance(content, str):
        raise TypeError(f"GitHub contents response missing content for {repo_path}")
    return base64.b64decode(content.replace("\n", ""), validate=True).decode("utf-8")


def canonical_state() -> dict[str, Any]:
    value = json.loads(github_text(PROJECT_STATE_PATH))
    if not isinstance(value, dict):
        raise TypeError("canonical project state must be a JSON object")
    return value


def is_android_termux(env: dict[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    prefix = values.get("PREFIX", "")
    android_root = values.get("ANDROID_ROOT", "")
    return prefix.startswith("/data/data/com.termux/") and bool(android_root)


def physical_source(state: dict[str, Any]) -> tuple[str, str]:
    physical = state.get("physical_gate") or {}
    if not isinstance(physical, dict):
        raise TypeError("physical_gate must be an object")
    status = str(physical.get("status") or "UNKNOWN")
    source = str(physical.get("qualified_source_commit") or "")
    return status, source


def write_record(source: str, payload: dict[str, Any]) -> Path:
    APP.mkdir(parents=True, exist_ok=True)
    path = APP / f"physical-resume-{source}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def newest_zip(since: float) -> Path | None:
    candidates = [
        p
        for p in Path.home().glob("guardian_physical_validation_*.zip")
        if p.is_file() and p.stat().st_mtime >= since - 2
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def resume() -> dict[str, Any]:
    now = time.time()
    if not is_android_termux():
        return {"status": "NOT_APPLICABLE_NON_TERMUX", "executed": False}

    state = canonical_state()
    status, source = physical_source(state)
    if not source:
        raise RuntimeError("canonical physical gate has no qualified source commit")
    if not any(token in status.upper() for token in ("BLOCK", "PENDING", "WAITING")):
        return {"status": "NO_PHYSICAL_ACTION_REQUIRED", "executed": False, "source": source}

    marker = APP / f"physical-resume-{source}.json"
    previous: dict[str, Any] = {}
    if marker.exists():
        try:
            loaded = json.loads(marker.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                previous = loaded
        except (OSError, json.JSONDecodeError):
            previous = {}
    preserved = previous.get("preserved_zip")
    if previous.get("status") == "DEVICE_PACKAGE_PRESERVED" and isinstance(preserved, str) and Path(preserved).exists():
        return {**previous, "executed": False, "deduplicated": True}

    APP.mkdir(parents=True, exist_ok=True)
    script = APP / f"termux_enroll_onepaste-{source}.sh"
    script.write_text(github_text(ENROLL_PATH, source), encoding="utf-8")
    script.chmod(0o700)

    started = time.time()
    result = run(["bash", str(script), "", source], timeout=900)
    package = newest_zip(started)
    if result.returncode != 0 or package is None:
        record = {
            "schema": "centinal26.autopilot.physical-resume.v1",
            "status": "DEVICE_COMMISSIONING_FAILED",
            "executed": True,
            "source": source,
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
            "updated_at": now,
        }
        write_record(source, record)
        return record

    evidence_dir = APP / "physical-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    preserved_path = evidence_dir / package.name
    if package.resolve() != preserved_path.resolve():
        preserved_path.write_bytes(package.read_bytes())

    record = {
        "schema": "centinal26.autopilot.physical-resume.v1",
        "status": "DEVICE_PACKAGE_PRESERVED",
        "executed": True,
        "source": source,
        "preserved_zip": str(preserved_path),
        "next_gate": "CONTROLLER_VERIFICATION_REQUIRED",
        "promotion_claimed": False,
        "updated_at": time.time(),
    }
    write_record(source, record)
    return record


def main() -> int:
    try:
        result = resume()
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "DEGRADED", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result.get("status") == "DEVICE_COMMISSIONING_FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
