from __future__ import annotations

import argparse
import json
from pathlib import Path

from .device_campaign import (
    DECISION_DEVICE_VALIDATED,
    DeviceCampaignError,
    prepare_device_campaign,
    resume_device_campaign,
    verify_device_campaign,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m centinal26.device_campaign_cli")
    sub = parser.add_subparsers(dest="command", required=True)

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
        if args.command == "prepare":
            report = prepare_device_campaign(args.campaign, boot_hook=args.boot_hook)
            print(json.dumps(report, sort_keys=True))
            return
        if args.command == "resume":
            report = resume_device_campaign(args.campaign, boot_hook=args.boot_hook)
            print(json.dumps(report, sort_keys=True))
            raise SystemExit(0 if report.get("decision") == DECISION_DEVICE_VALIDATED else 3)
        valid = verify_device_campaign(args.campaign)
        print(json.dumps({"campaign": str(args.campaign), "valid": valid}, sort_keys=True))
        raise SystemExit(0 if valid else 1)
    except DeviceCampaignError as error:
        print(json.dumps({"error": str(error), "valid": False}, sort_keys=True))
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
