from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def load_source(path: str | Path) -> Json:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("continuity schema source must be a JSON object")
    if value.get("schema") != "frost.automation.continuity_model_source.v1":
        raise ValueError("unsupported continuity schema source")
    if not isinstance(value.get("entity_types"), list) or not value["entity_types"]:
        raise ValueError("entity_types must be a non-empty list")
    if len(value["entity_types"]) != len(set(value["entity_types"])):
        raise ValueError("entity_types must be unique")
    return value


def generate_json_schema(source: Mapping[str, Any]) -> Json:
    entity_types = list(source["entity_types"])
    statuses = list(source["epistemic_statuses"])
    artifact = dict(source["artifact"])
    invariants = dict(source["authority_invariants"])
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://centinal26.local/schemas/continuity_migration_proposal.schema.json",
        "title": "Centinal26 Continuity Migration Proposal",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema",
            "status",
            "source_system",
            "export_version",
            "source_digest",
            "authority",
            "entities",
            "relationships",
            "artifacts",
        ],
        "properties": {
            "schema": {"const": source["proposal_schema"]},
            "status": {"const": invariants["status"]},
            "source_system": {"type": "string", "minLength": 1},
            "export_version": {"type": "string", "minLength": 1},
            "source_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "authority": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "canonical_target",
                    "machine_continuation",
                    "execution_authority",
                    "automatic_epistemic_promotion",
                    "automatic_contradiction_resolution",
                    "alias_or_current_pointer_update",
                ],
                "properties": {
                    "canonical_target": {"type": "string", "minLength": 1},
                    "machine_continuation": {"const": invariants["machine_continuation"]},
                    "execution_authority": {"const": invariants["execution_authority"]},
                    "automatic_epistemic_promotion": {
                        "const": invariants["automatic_epistemic_promotion"]
                    },
                    "automatic_contradiction_resolution": {
                        "const": invariants["automatic_contradiction_resolution"]
                    },
                    "alias_or_current_pointer_update": {
                        "const": invariants["alias_or_current_pointer_update"]
                    },
                },
            },
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "stable_id",
                        "source_id",
                        "entity_type",
                        "epistemic_status",
                        "revision_parent",
                        "payload",
                    ],
                    "properties": {
                        "stable_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                        "source_id": {"type": "string", "minLength": 1},
                        "entity_type": {"enum": entity_types},
                        "epistemic_status": {"type": ["string", "null"], "enum": [*statuses, None]},
                        "revision_parent": {"type": ["string", "null"]},
                        "payload": {"type": "object"},
                    },
                },
            },
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(source["relationship"]["required"]),
                    "properties": {
                        "source_id": {"type": "string", "minLength": 1},
                        "relation": {"type": "string", "minLength": 1},
                        "target_id": {"type": "string", "minLength": 1},
                        "source_endpoint_type": {"type": "string", "minLength": 1},
                        "target_endpoint_type": {"type": "string", "minLength": 1},
                    },
                },
            },
            "artifacts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(artifact["required"]),
                    "properties": {
                        "artifact_id": {"type": "string", "minLength": 1},
                        "sha256": {"type": "string", "pattern": artifact["sha256_pattern"]},
                        "verification": {"type": "string", "minLength": 1},
                        "media_type": {"type": ["string", "null"]},
                        "logical_ref": {"type": ["string", "null"]},
                    },
                },
            },
        },
    }


def generate_markdown(source: Mapping[str, Any]) -> str:
    entity_lines = "\n".join(f"- `{name}`" for name in source["entity_types"])
    status_lines = "\n".join(f"- `{name}`" for name in source["epistemic_statuses"])
    return (
        "# Generated continuity schema reference\n\n"
        f"Model version: `{source['model_version']}`  \n"
        f"Proposal schema: `{source['proposal_schema']}`\n\n"
        "This file is generated from `automation/continuity_schema_source.json`. "
        "Do not edit it independently.\n\n"
        "## Entity types\n\n"
        f"{entity_lines}\n\n"
        "## Epistemic statuses\n\n"
        f"{status_lines}\n\n"
        "## Authority invariants\n\n"
        "- proposal status is `PROPOSAL_ONLY`;\n"
        "- machine continuation remains `automation/PROJECT_STATE.json`;\n"
        "- execution authority is false;\n"
        "- automatic epistemic promotion is false;\n"
        "- automatic contradiction resolution is false;\n"
        "- alias/current-pointer mutation is false.\n"
    )


def write_generated(source_path: str | Path, schema_path: str | Path, docs_path: str | Path) -> None:
    source = load_source(source_path)
    Path(schema_path).write_text(
        json.dumps(generate_json_schema(source), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(docs_path).write_text(generate_markdown(source), encoding="utf-8")
