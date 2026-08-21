"""Register, validate, and list reusable Frost Forge abilities.

This helper does not grant authority. It records tools/adapters that have already
been built within an authorized scope so later automation can discover and reuse
them instead of rebuilding equivalent machinery.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = Path("automation/abilities/registry.json")
REQUIRED_FIELDS = {
    "id",
    "name",
    "kind",
    "source",
    "interface",
    "verification",
    "provenance",
    "status",
}
ALLOWED_STATUS = {"EXPERIMENTAL", "VERIFIED", "SUPERSEDED", "BLOCKED"}


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("abilities"), list):
        raise TypeError("registry must contain an abilities list")
    return data


def validate_ability(ability: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - ability.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    status = ability.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"invalid status: {status!r}")
    if not isinstance(ability.get("source"), dict):
        errors.append("source must be an object")
    if not isinstance(ability.get("verification"), dict):
        errors.append("verification must be an object")
    if not isinstance(ability.get("provenance"), dict):
        errors.append("provenance must be an object")
    return errors


def validate_registry(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, ability in enumerate(data.get("abilities", [])):
        if not isinstance(ability, dict):
            errors.append(f"abilities[{index}] must be an object")
            continue
        ability_id = ability.get("id")
        if isinstance(ability_id, str):
            if ability_id in seen:
                errors.append(f"duplicate ability id: {ability_id}")
            seen.add(ability_id)
        for error in validate_ability(ability):
            errors.append(f"abilities[{index}]: {error}")
    return errors


def register_ability(path: Path, ability_path: Path) -> None:
    data = load_registry(path)
    ability = json.loads(ability_path.read_text(encoding="utf-8"))
    if not isinstance(ability, dict):
        raise TypeError("ability file must contain a JSON object")
    errors = validate_ability(ability)
    if errors:
        raise ValueError("; ".join(errors))
    ability_id = ability["id"]
    if any(item.get("id") == ability_id for item in data["abilities"]):
        raise ValueError(f"ability already exists: {ability_id}")
    data["abilities"].append(ability)
    data["abilities"].sort(key=lambda item: item["id"])
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list")
    sub.add_parser("validate")
    register = sub.add_parser("register")
    register.add_argument("ability", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "list":
            data = load_registry(args.registry)
            for item in data["abilities"]:
                print(f"{item['id']}\t{item['status']}\t{item['name']}")
            return 0
        if args.command == "validate":
            errors = validate_registry(load_registry(args.registry))
            if errors:
                for error in errors:
                    print(error)
                return 1
            print("ABILITY_REGISTRY_VALID")
            return 0
        if args.command == "register":
            register_ability(args.registry, args.ability)
            print("ABILITY_REGISTERED")
            return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
