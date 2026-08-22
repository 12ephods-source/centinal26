"""Register, validate, discover, and list reusable Frost Forge abilities.

This helper does not grant authority. It records tools/adapters that have already
been built within an authorized scope so later automation can discover and reuse
them instead of rebuilding equivalent machinery.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
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
    "lifecycle",
    "status",
}
OBJECT_FIELDS = {"source", "interface", "verification", "provenance", "lifecycle"}
ALLOWED_STATUS = {"EXPERIMENTAL", "VERIFIED", "SUPERSEDED", "BLOCKED"}
ABILITY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
REQUIRED_POLICY_REQUIREMENTS = {
    "bounded_scope",
    "source_preserved",
    "tests_or_verification_preserved",
    "provenance_preserved",
    "interface_documented",
    "rollback_or_removal_path",
    "no_authority_expansion",
}


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("registry must be a JSON object")
    return data


def load_ability(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"ability file must contain a JSON object: {path}")
    return data


def validate_ability(ability: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - ability.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")

    for field in ("id", "name", "kind"):
        value = ability.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    ability_id = ability.get("id")
    if isinstance(ability_id, str) and ability_id:
        if not ABILITY_ID_RE.fullmatch(ability_id):
            errors.append("id must use lowercase letters, digits, '.', '_', '/', or '-'")
        if any(segment in {"", ".", ".."} for segment in ability_id.split("/")):
            errors.append("id must not contain empty, current, or parent path segments")

    status = ability.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"invalid status: {status!r}")

    for field in sorted(OBJECT_FIELDS):
        value = ability.get(field)
        if not isinstance(value, dict) or not value:
            errors.append(f"{field} must be a non-empty object")

    lifecycle = ability.get("lifecycle")
    if isinstance(lifecycle, dict) and lifecycle:
        paths = [lifecycle.get("rollback"), lifecycle.get("removal")]
        if not any(isinstance(item, str) and item.strip() for item in paths):
            errors.append("lifecycle must define a non-empty rollback or removal path")

    return errors


def validate_registry(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "1.0":
        errors.append("schema_version must equal '1.0'")

    policy = data.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        if policy.get("missing_capability") != "BUILD_TEST_REGISTER_REUSE_WHEN_AUTHORIZED":
            errors.append("policy.missing_capability is invalid")
        if policy.get("external_boundary") != "RECORD_BLOCKER_AND_CONTINUE":
            errors.append("policy.external_boundary is invalid")
        requirements = policy.get("requirements")
        if not isinstance(requirements, list) or not all(
            isinstance(item, str) for item in requirements
        ):
            errors.append("policy.requirements must be a list of strings")
        else:
            missing_requirements = sorted(REQUIRED_POLICY_REQUIREMENTS - set(requirements))
            if missing_requirements:
                errors.append(
                    "policy.requirements missing: " + ", ".join(missing_requirements)
                )

    abilities = data.get("abilities")
    if not isinstance(abilities, list):
        errors.append("registry must contain an abilities list")
        return errors

    seen: set[str] = set()
    for index, ability in enumerate(abilities):
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


def manifest_paths(registry_path: Path, manifests_dir: Path | None = None) -> list[Path]:
    directory = manifests_dir if manifests_dir is not None else registry_path.parent
    registry_resolved = registry_path.resolve()
    return [
        path
        for path in sorted(directory.glob("*.json"))
        if path.resolve() != registry_resolved
    ]


def merge_manifests(
    registry: dict[str, Any],
    paths: list[Path],
) -> tuple[dict[str, Any], int, int]:
    registry_errors = validate_registry(registry)
    if registry_errors:
        raise ValueError("invalid registry: " + "; ".join(registry_errors))

    merged = copy.deepcopy(registry)
    existing = {item["id"]: item for item in merged["abilities"]}
    added_count = 0
    existing_count = 0

    for path in paths:
        ability = load_ability(path)
        errors = validate_ability(ability)
        if errors:
            raise ValueError(f"invalid ability manifest {path}: " + "; ".join(errors))

        ability_id = ability["id"]
        prior = existing.get(ability_id)
        if prior is not None:
            if prior != ability:
                raise ValueError(
                    f"ability manifest conflicts with registry entry: {ability_id}"
                )
            existing_count += 1
            continue

        merged["abilities"].append(ability)
        existing[ability_id] = ability
        added_count += 1

    merged["abilities"].sort(key=lambda item: item["id"])
    post_errors = validate_registry(merged)
    if post_errors:
        raise ValueError("effective registry invalid: " + "; ".join(post_errors))
    return merged, added_count, existing_count


def effective_registry(
    path: Path,
    manifests_dir: Path | None = None,
) -> dict[str, Any]:
    merged, _, _ = merge_manifests(
        load_registry(path),
        manifest_paths(path, manifests_dir),
    )
    return merged


def write_registry_atomic(path: Path, data: dict[str, Any]) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    try:
        temp_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def register_ability(path: Path, ability_path: Path) -> None:
    data = load_registry(path)
    registry_errors = validate_registry(data)
    if registry_errors:
        raise ValueError("invalid registry: " + "; ".join(registry_errors))

    ability = load_ability(ability_path)
    errors = validate_ability(ability)
    if errors:
        raise ValueError("; ".join(errors))

    ability_id = ability["id"]
    if any(item.get("id") == ability_id for item in data["abilities"]):
        raise ValueError(f"ability already exists: {ability_id}")

    data["abilities"].append(ability)
    data["abilities"].sort(key=lambda item: item["id"])
    post_errors = validate_registry(data)
    if post_errors:
        raise ValueError("updated registry invalid: " + "; ".join(post_errors))
    write_registry_atomic(path, data)


def sync_manifests(path: Path, manifests_dir: Path | None = None) -> tuple[int, int]:
    merged, added_count, existing_count = merge_manifests(
        load_registry(path),
        manifest_paths(path, manifests_dir),
    )
    if added_count:
        write_registry_atomic(path, merged)
    return added_count, existing_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--manifests-dir", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list")
    sub.add_parser("validate")
    sub.add_parser("sync-manifests")
    register = sub.add_parser("register")
    register.add_argument("ability", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "list":
            data = effective_registry(args.registry, args.manifests_dir)
            for item in data["abilities"]:
                print(f"{item['id']}\t{item['status']}\t{item['name']}")
            return 0
        if args.command == "validate":
            effective_registry(args.registry, args.manifests_dir)
            print("ABILITY_REGISTRY_VALID")
            return 0
        if args.command == "sync-manifests":
            added, existing = sync_manifests(args.registry, args.manifests_dir)
            print(f"ABILITY_MANIFESTS_SYNCED added={added} existing={existing}")
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
