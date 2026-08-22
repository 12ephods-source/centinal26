from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SOFTWARE_REQUIRED = (
    "repo_sync",
    "repo_clean",
    "pair_ok",
    "skynet_ok",
    "state_integrity_ok",
    "recovery_ok",
    "security_policy_ok",
)

DEPLOYMENT_REQUIRED = SOFTWARE_REQUIRED + (
    "device_boot_ok",
    "device_restart_ok",
    "device_exec_ok",
    "device_audit_ok",
)


@dataclass(frozen=True)
class ReleaseProfile:
    software_release_complete: bool
    deployed_app_complete: bool
    software_missing: tuple[str, ...]
    deployment_missing: tuple[str, ...]


def evaluate(checks: dict[str, object]) -> ReleaseProfile:
    normalized = {key: bool(value) for key, value in checks.items()}
    software_missing = tuple(
        key for key in SOFTWARE_REQUIRED if not normalized.get(key, False)
    )
    deployment_missing = tuple(
        key for key in DEPLOYMENT_REQUIRED if not normalized.get(key, False)
    )
    return ReleaseProfile(
        software_release_complete=not software_missing,
        deployed_app_complete=not deployment_missing,
        software_missing=software_missing,
        deployment_missing=deployment_missing,
    )


def evaluate_state_file(path: Path) -> dict[str, object]:
    state = json.loads(path.read_text())
    profile = evaluate(state.get("checks", {}))
    return {
        "release": state.get("release"),
        "software_release_complete": profile.software_release_complete,
        "deployed_app_complete": profile.deployed_app_complete,
        "software_missing": list(profile.software_missing),
        "deployment_missing": list(profile.deployment_missing),
        "policy": {
            "finished_software_product_requires_device_evidence": False,
            "finished_deployed_app_requires_device_evidence": True,
        },
    }
