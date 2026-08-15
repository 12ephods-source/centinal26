from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(
    os.environ.get(
        "AUTOMATION_INTELLIGENCE_GATE_ROOT",
        Path.home() / ".automation_intelligence_gate",
    )
)
OUT = ROOT / "independent_verification.json"


def load(name: str) -> dict[str, Any]:
    path = ROOT / name
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(checks: dict[str, bool], name: str, condition: bool) -> None:
    checks[name] = bool(condition)


def main() -> int:
    checks: dict[str, bool] = {}
    pre = load("project_pre_reboot.json")
    post = load("post_reboot.json")
    endurance = load("endurance_report.json")
    sync = load("device_sync.json")
    samples_path = ROOT / "endurance_samples.jsonl"
    samples = [
        json.loads(line)
        for line in samples_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    require(checks, "pre_phase", pre.get("phase") == "AWAITING_REBOOT")
    require(
        checks,
        "legacy_not_current_blocker",
        pre.get("current_release", {}).get("legacy_rc4_required") is False,
    )
    require(checks, "post_phase", post.get("phase") == "PHYSICAL_VALIDATED")
    require(
        checks,
        "real_reboot",
        bool(post.get("pre_boot_id")) and post.get("pre_boot_id") != post.get("post_boot_id"),
    )
    for key in (
        "reboot_change",
        "boot_autostart",
        "controller_return",
        "post_reboot_job",
        "event_chain",
        "heartbeat_freshness",
    ):
        require(checks, f"post_{key}", post.get(key) == "PASS")

    require(checks, "endurance_status", endurance.get("status") == "PASS")
    require(
        checks,
        "physical_android",
        endurance.get("platform") == "android/termux"
        and endurance.get("physical_android_validated") is True,
    )
    require(checks, "endurance_samples", int(endurance.get("samples", 0)) >= 61)
    require(checks, "endurance_window", int(endurance.get("elapsed_seconds", 0)) >= 3500)
    require(checks, "endurance_health", int(endurance.get("unhealthy_samples", -1)) == 0)
    require(checks, "recovery_drill", endurance.get("recovery_drill_pass") is True)
    require(checks, "unsupported_denial", endurance.get("unsupported_command_denied") is True)
    require(checks, "sample_count_matches", len(samples) == int(endurance.get("samples", -1)))
    require(checks, "sample_hash_matches", sha(samples_path) == endurance.get("samples_sha256"))
    require(
        checks,
        "all_samples_healthy",
        bool(samples) and all(sample.get("healthy") is True for sample in samples),
    )
    require(
        checks,
        "single_endurance_boot",
        bool(samples) and all(sample.get("boot_id") == endurance.get("boot_id") for sample in samples),
    )

    require(checks, "device_sync_status", sync.get("status") == "PASS")
    require(
        checks,
        "device_sync_comment",
        bool(sync.get("comment_id")) and bool(sync.get("comment_url")),
    )
    require(
        checks,
        "device_sync_endurance_binding",
        sync.get("endurance_sha256") == sha(ROOT / "endurance_report.json"),
    )

    decision = "PASS" if checks and all(checks.values()) else "FAIL"
    evidence = {
        name: sha(ROOT / name)
        for name in (
            "project_pre_reboot.json",
            "pre_reboot.json",
            "post_reboot.json",
            "endurance_report.json",
            "endurance_samples.jsonl",
            "device_sync.json",
        )
    }
    payload = {
        "schema": "centinal26.automation_project_finalization_verification/v1",
        "verifier_id": "independent-python-evidence-verifier/v1",
        "decision": decision,
        "checks": checks,
        "evidence_sha256": evidence,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["verification_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0 if decision == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
