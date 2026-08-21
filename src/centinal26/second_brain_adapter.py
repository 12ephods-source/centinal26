from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

Json = dict[str, Any]

SECOND_BRAIN_SOURCE = "ai-first-second-brain/v0.2.0"
PROPOSAL_SCHEMA = "frost.automation.knowledge_proposal_bundle.v1"

COLLECTION_ENTITY_TYPES = {
    "decisions": "decision",
    "experiments": "experiment",
    "findings": "finding",
    "security_cases": "security_case",
    "tasks": "knowledge_task",
    "code_modules": "code_module",
    "test_plans": "test_plan",
    "library": "artifact",
    "runs": "run",
    "theory": "theory_claim",
    "evidence": "evidence",
    "environments": "environment",
    "ai_sessions": "ai_session",
    "workbench": "workbench_capture",
    "revisions": "knowledge_revision",
}


class SecondBrainProposalError(ValueError):
    """The source export cannot be represented as a safe canonical proposal."""


class ProposalConflict(SecondBrainProposalError):
    """A stable proposal identity was reused with different immutable content."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SecondBrainProposalError(f"{name} must be a non-empty string")
    return value.strip()


def _parse_json_object(value: Any) -> Json:
    if isinstance(value, dict):
        return json.loads(canonical_json(value))
    if not value:
        return {}
    if not isinstance(value, str):
        return {"unparsed_value": value}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"unparsed_text": value}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _stable_id(source_system: str, entity_type: str, source_id: str) -> str:
    digest = hashlib.sha256(
        f"{source_system}\0{entity_type}\0{source_id}".encode("utf-8")
    ).hexdigest()
    return f"knowledge-proposal:{entity_type}:{digest[:24]}"


def _relationship_id(source_system: str, relationship: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        f"{source_system}\0{canonical_json(dict(relationship))}".encode("utf-8")
    ).hexdigest()
    return f"knowledge-relation:{digest[:24]}"


def _entity_proposal(
    *,
    source_system: str,
    entity_type: str,
    record: Mapping[str, Any],
    project_id: str,
    artifact_hashes: Mapping[str, str],
) -> Json:
    source_record = json.loads(canonical_json(dict(record)))
    source_id = _required_text(source_record.get("id"), f"{entity_type}.id")
    record_sha256 = sha256_json(source_record)
    proposal: Json = {
        "proposal_id": _stable_id(source_system, entity_type, source_id),
        "source_system": source_system,
        "source_id": source_id,
        "entity_type": entity_type,
        "source_record_sha256": record_sha256,
        "project_id": source_record.get("project_id") or project_id,
        "epistemic_status": source_record.get("epistemic_status", "Unknown"),
        "provenance": _parse_json_object(source_record.get("provenance_json", {})),
        "record": source_record,
        "authority": "proposal_only",
        "execution_authorized": False,
        "truth_promoted": False,
    }

    if entity_type == "artifact":
        declared = source_record.get("checksum_sha256", "")
        observed = artifact_hashes.get(source_id, "")
        if declared and observed and declared != observed:
            raise SecondBrainProposalError(
                f"artifact checksum mismatch for {source_id}: declared={declared} observed={observed}"
            )
        if declared and observed:
            verification = "VERIFIED_MATCH"
        elif declared:
            verification = "DECLARED_UNVERIFIED"
        else:
            verification = "NOT_DECLARED"
        proposal["artifact_integrity"] = {
            "declared_sha256": declared,
            "observed_sha256": observed,
            "status": verification,
        }
    return proposal


def _source_records(export: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    project = export.get("project")
    if not isinstance(project, dict):
        raise SecondBrainProposalError("export.project must be an object")
    records: list[tuple[str, Mapping[str, Any]]] = [("project", project)]
    for collection, entity_type in COLLECTION_ENTITY_TYPES.items():
        values = export.get(collection, [])
        if values is None:
            continue
        if not isinstance(values, list):
            raise SecondBrainProposalError(f"export.{collection} must be a list")
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                raise SecondBrainProposalError(
                    f"export.{collection}[{index}] must be an object"
                )
            records.append((entity_type, value))
    return records


def _relationship_proposals(
    export: Mapping[str, Any],
    *,
    source_system: str,
    known_ids: set[str],
    strict_relationships: bool,
) -> list[Json]:
    relationships: list[Json] = []
    raw_links = export.get("links", []) or []
    if not isinstance(raw_links, list):
        raise SecondBrainProposalError("export.links must be a list")
    for index, raw in enumerate(raw_links):
        if not isinstance(raw, dict):
            raise SecondBrainProposalError(f"export.links[{index}] must be an object")
        relation = {
            "from_type": _required_text(raw.get("from_type"), "link.from_type"),
            "from_id": _required_text(raw.get("from_id"), "link.from_id"),
            "relation": _required_text(raw.get("relation"), "link.relation"),
            "to_type": _required_text(raw.get("to_type"), "link.to_type"),
            "to_id": _required_text(raw.get("to_id"), "link.to_id"),
        }
        missing = [
            endpoint
            for endpoint in (relation["from_id"], relation["to_id"])
            if endpoint not in known_ids
        ]
        if missing and strict_relationships:
            raise SecondBrainProposalError(
                f"relationship references source IDs absent from export: {missing}"
            )
        relationships.append(
            {
                "relationship_id": _relationship_id(source_system, relation),
                "source_system": source_system,
                **relation,
                "endpoint_status": "RESOLVED_IN_EXPORT" if not missing else "UNRESOLVED_EXTERNAL",
                "missing_source_ids": missing,
                "authority": "proposal_only",
            }
        )
    relationships.sort(key=lambda item: item["relationship_id"])
    return relationships


def build_proposal_bundle(
    export: Mapping[str, Any],
    *,
    source_system: str = SECOND_BRAIN_SOURCE,
    artifact_hashes: Mapping[str, str] | None = None,
    strict_relationships: bool = False,
) -> Json:
    """Convert a Second Brain export into deterministic proposal-only canonical records.

    This function performs no file, database, event-store, network, or execution writes.
    It intentionally preserves source IDs, record hashes, epistemic state, provenance,
    relationships, and declared artifact hashes so a later authorized canonicalizer can
    make an explicit promotion decision.
    """

    source_system = _required_text(source_system, "source_system")
    artifact_hashes = artifact_hashes or {}
    project = export.get("project")
    if not isinstance(project, dict):
        raise SecondBrainProposalError("export.project must be an object")
    project_id = _required_text(project.get("id"), "project.id")

    source_schema_version = export.get("schema_version")
    if source_schema_version is not None and not isinstance(source_schema_version, str):
        raise SecondBrainProposalError("schema_version must be a string when present")

    proposals = [
        _entity_proposal(
            source_system=source_system,
            entity_type=entity_type,
            record=record,
            project_id=project_id,
            artifact_hashes=artifact_hashes,
        )
        for entity_type, record in _source_records(export)
    ]
    proposals.sort(key=lambda item: item["proposal_id"])

    proposal_ids = [item["proposal_id"] for item in proposals]
    if len(proposal_ids) != len(set(proposal_ids)):
        raise ProposalConflict("duplicate stable proposal identity in source export")

    known_source_ids = {item["source_id"] for item in proposals}
    relationships = _relationship_proposals(
        export,
        source_system=source_system,
        known_ids=known_source_ids,
        strict_relationships=strict_relationships,
    )

    body: Json = {
        "schema": PROPOSAL_SCHEMA,
        "source_system": source_system,
        "source_schema_version": source_schema_version or "unknown",
        "source_generated_utc": export.get("generated_utc", ""),
        "source_project_id": project_id,
        "authority": "proposal_only",
        "execution_authorized": False,
        "truth_promoted": False,
        "records": proposals,
        "relationships": relationships,
        "record_count": len(proposals),
        "relationship_count": len(relationships),
    }
    body["bundle_sha256"] = sha256_json(body)
    return body


def verify_proposal_bundle(bundle: Mapping[str, Any]) -> bool:
    if bundle.get("schema") != PROPOSAL_SCHEMA:
        return False
    expected = bundle.get("bundle_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        return False
    body = dict(bundle)
    body.pop("bundle_sha256", None)
    return sha256_json(body) == expected


@dataclass
class ProposalIndex:
    """In-memory conflict/idempotency gate for proposal bundles.

    The index is deliberately not a persistence layer. It models the exact behavior that
    a later canonical continuity writer must preserve: stable IDs may be replayed only
    when immutable source content is identical.
    """

    records: dict[str, str] = field(default_factory=dict)
    relationships: dict[str, str] = field(default_factory=dict)

    def ingest(self, bundle: Mapping[str, Any]) -> Json:
        if not verify_proposal_bundle(bundle):
            raise SecondBrainProposalError("proposal bundle hash verification failed")

        new_records = 0
        duplicate_records = 0
        new_relationships = 0
        duplicate_relationships = 0

        staged_records = dict(self.records)
        staged_relationships = dict(self.relationships)

        records = bundle.get("records", [])
        relationships = bundle.get("relationships", [])
        if not isinstance(records, list) or not isinstance(relationships, list):
            raise SecondBrainProposalError("records and relationships must be lists")

        for record in records:
            if not isinstance(record, dict):
                raise SecondBrainProposalError("proposal record must be an object")
            proposal_id = _required_text(record.get("proposal_id"), "proposal_id")
            record_sha = _required_text(record.get("source_record_sha256"), "source_record_sha256")
            existing = staged_records.get(proposal_id)
            if existing is not None and existing != record_sha:
                raise ProposalConflict(f"proposal identity changed content: {proposal_id}")
            if existing is None:
                staged_records[proposal_id] = record_sha
                new_records += 1
            else:
                duplicate_records += 1

        for relationship in relationships:
            if not isinstance(relationship, dict):
                raise SecondBrainProposalError("relationship proposal must be an object")
            relationship_id = _required_text(
                relationship.get("relationship_id"), "relationship_id"
            )
            digest = sha256_json(relationship)
            existing = staged_relationships.get(relationship_id)
            if existing is not None and existing != digest:
                raise ProposalConflict(
                    f"relationship identity changed content: {relationship_id}"
                )
            if existing is None:
                staged_relationships[relationship_id] = digest
                new_relationships += 1
            else:
                duplicate_relationships += 1

        self.records = staged_records
        self.relationships = staged_relationships
        return {
            "status": "accepted_proposal_only",
            "new_records": new_records,
            "duplicate_records": duplicate_records,
            "new_relationships": new_relationships,
            "duplicate_relationships": duplicate_relationships,
            "execution_authorized": False,
            "truth_promoted": False,
        }


def load_export(path: str | Path) -> Json:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SecondBrainProposalError("Second Brain export root must be an object")
    return value
