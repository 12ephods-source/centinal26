from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from openquest.builder import build_level_one_character, list_options
from openquest.validator import export_character


def _parse_abilities(value: str) -> dict[str, int]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"abilities must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("abilities must decode to a JSON object")
    try:
        return {str(key): int(score) for key, score in payload.items()}
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("ability scores must be integers") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openquest", description="OpenQuest character creator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    options = subparsers.add_parser("options", help="List legal construction options")
    options.add_argument("--ruleset", default="srd-5.2.1")

    create = subparsers.add_parser("create", help="Create, validate, and export a level-1 character")
    create.add_argument("--name", required=True)
    create.add_argument("--ruleset", default="srd-5.2.1")
    create.add_argument("--class", dest="class_name", required=True)
    create.add_argument("--species", required=True)
    create.add_argument("--background", required=True)
    create.add_argument("--skill", action="append", dest="skills", default=[])
    create.add_argument("--abilities", required=True, type=_parse_abilities)
    create.add_argument("--armor-class", type=int, default=10)
    create.add_argument("--output", type=Path)
    return parser


def _run_options(args: argparse.Namespace) -> int:
    try:
        options = list_options(args.ruleset)
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(asdict(options), indent=2, sort_keys=True))
    return 0


def _run_create(args: argparse.Namespace) -> int:
    result = build_level_one_character(
        name=args.name,
        ability_scores=args.abilities,
        class_name=args.class_name,
        species=args.species,
        background=args.background,
        skill_proficiencies=args.skills,
        ruleset=args.ruleset,
        armor_class=args.armor_class,
    )
    if not result.valid or result.character is None:
        payload = {
            "schema": "openquest.build-result.v1",
            "status": "FAIL",
            "gates": [
                {"gate": gate.gate, "status": gate.status.value, "detail": gate.detail}
                for gate in result.gates
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2

    rendered = export_character(result.character, list(result.gates))
    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "options":
        return _run_options(args)
    if args.command == "create":
        return _run_create(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
