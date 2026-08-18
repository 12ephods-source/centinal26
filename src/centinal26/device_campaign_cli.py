from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import uuid
from pathlib import Path

from .device_campaign import (
    DECISION_PERSISTENT_VALIDATED,
    DeviceCampaignError,
    prepare_device_campaign,
    resume_device_campaign,
    verify_device_campaign,
)

DEVICE_ID_SCHEMA = "centinal26-device-identity-v1"
DEVICE_BINDING_SCHEMA = "centinal26-device-campaign-binding-v1"
DEVICE_BINDING_NAME = "device-identity-binding.json"
_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _state_root() -> Path:
    return Path(
        os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26")
    ).expanduser().resolve()


def _device_id_path() -> Path:
    return _state_root() / "device-identity.json"


def _valid_device_id(value: object) -> bool:
    return isinstance(value, str) and bool(_DEVICE_ID_RE.fullmatch(value))


def _read_json_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DeviceCampaignError(f"cannot read device identity state: {path}: {error}") from error
    if not isinstance(value, dict):
        raise DeviceCampaignError(f"device identity state is not a JSON object: {path}")
    return value


def _write_json_secure(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    rendered = json.dumps(value, sort_keys=True, indent=2) + "\n"
    try:
        temporary.write_text(rendered, encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _github_config_device_id() -> str | None:
    path = Path.home() / ".automation_os_github" / "config.json"
    if not path.is_file():
        return None
    value = _read_json_object(path)
    if value.get("schema") != "centinal26-github-worker-config-v1":
        return None
    candidate = value.get("automation_device_id")
    return candidate if _valid_device_id(candidate) else None


def _load_or_create_device_id() -> str:
    path = _device_id_path()
    env_id = os.environ.get("AUTOMATION_DEVICE_ID", "").strip() or None
    if env_id is not None and not _valid_device_id(env_id):
        raise DeviceCampaignError("AUTOMATION_DEVICE_ID is invalid")
    config_id = _github_config_device_id()

    if path.is_file():
        value = _read_json_object(path)
        persisted = value.get("device_id")
        if value.get("schema") != DEVICE_ID_SCHEMA or not _valid_device_id(persisted):
            raise DeviceCampaignError("persisted device identity is invalid")
        if env_id is not None and env_id != persisted:
            raise DeviceCampaignError(
                "AUTOMATION_DEVICE_ID conflicts with persisted device identity"
            )
        if config_id is not None and config_id != persisted:
            raise DeviceCampaignError(
                "GitHub worker identity conflicts with persisted device identity"
            )
        return persisted

    device_id = env_id or config_id
    if device_id is None:
        device_id = f"android-{platform.machine()}-{uuid.uuid4()}"
    if not _valid_device_id(device_id):
        raise DeviceCampaignError("generated device identity is invalid")
    _write_json_secure(path, {"schema": DEVICE_ID_SCHEMA, "device_id": device_id})
    return device_id


def _binding_path(campaign: Path) -> Path:
    return campaign.expanduser().resolve() / DEVICE_BINDING_NAME


def _write_device_binding(campaign: Path, device_id: str) -> None:
    path = _binding_path(campaign)
    if path.exists():
        raise DeviceCampaignError(f"device binding already exists: {path}")
    _write_json_secure(
        path,
        {
            "schema": DEVICE_BINDING_SCHEMA,
            "device_id": device_id,
            "device_id_sha256": hashlib.sha256(device_id.encode("utf-8")).hexdigest(),
            "source_commit": os.environ.get("CENTINAL26_CAMPAIGN_SOURCE_SHA"),
        },
    )


def _verify_device_binding(campaign: Path, device_id: str) -> None:
    path = _binding_path(campaign)
    value = _read_json_object(path)
    found = value.get("device_id")
    digest = value.get("device_id_sha256")
    expected_digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
    if value.get("schema") != DEVICE_BINDING_SCHEMA:
        raise DeviceCampaignError("device campaign binding schema is invalid")
    if found != device_id or digest != expected_digest:
        raise DeviceCampaignError(
            "device campaign belongs to a different physical Termux identity"
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m centinal26.device_campaign_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("identity")

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--campaign", type=Path, required=True)
    prepare.add_argument("--boot-hook", type=Path, required=True)

    resume = sub.add_parser("resume")
    resume.add_argument("--campaign", type=Path, required=True)
    resume.add_argument("--boot-hook", type=Path)

    verify = sub.add_parser("verify")
    verify.add_argument("--campaign", type=Path, required=True)

    args = parser.parse_args()
    try:
        device_id = _load_or_create_device_id()
        if args.command == "identity":
            print(json.dumps({"device_id": device_id}, sort_keys=True))
            return
        if args.command == "prepare":
            report = prepare_device_campaign(args.campaign, boot_hook=args.boot_hook)
            _write_device_binding(args.campaign, device_id)
            print(json.dumps({**report, "device_id": device_id}, sort_keys=True))
            return
        _verify_device_binding(args.campaign, device_id)
        if args.command == "resume":
            report = resume_device_campaign(args.campaign, boot_hook=args.boot_hook)
            print(json.dumps({**report, "device_id": device_id}, sort_keys=True))
            raise SystemExit(
                0 if report.get("decision") == DECISION_PERSISTENT_VALIDATED else 3
            )
        valid = verify_device_campaign(args.campaign)
        print(
            json.dumps(
                {"campaign": str(args.campaign), "device_id": device_id, "valid": valid},
                sort_keys=True,
            )
        )
        raise SystemExit(0 if valid else 1)
    except DeviceCampaignError as error:
        print(json.dumps({"error": str(error), "valid": False}, sort_keys=True))
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
