from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .continuity_proposal import ContinuityProposalAdapter, ContinuityProposalReceipt
from .object_store import CanonicalObjectStore

Json = dict[str, Any]
SECOND_BRAIN_V02 = "AI-First Second Brain v0.2.0"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_COLLECTION_TYPES = {
    "decisions": "decision",
    "experiments": "experiment",
    "findings": "finding",
    "security_cases": "security_case",
    "tasks": "knowledge_task",
    "code_modules": "code_module",
    "test_plans": "test_plan",
    "library": "artifact_metadata",
    "runs": "run",
    "theory": "theory_claim",
    "evidence": "evidence",
    "environments": "environment",
    "ai_sessions": "ai_session",
    "workbench": "workbench_capture",
    "revisions": "knowledge_revision",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _record_hash(record: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(dict(record))).hexdigest()


def _required_id(record: Mapping[str, Any], label: str) -> str:
    value = record.get("id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.id is required")
    return value.strip()


def _entity(source_table: str, entity_type: str, record: Mapping[str, Any]) -> Json:
    source_id = _required_id(record, source_table)
    payload = json.loads(_canonical_bytes(dict(record)))
    return {
        "source_id": source_id,
        "entity_type": entity_type,
        "epistemic_status": record.get("epistemic_status"),
        "revision_parent": None,
        "payload": {
            "source_table": source_table,
            "source_record_sha256": _record_hash(record),
            "record": payload,
        },
    }


def normalize_second_brain_v02_context(context: Mapping[str, Any]) -> Json:
    """Translate the historical v0.2 `export-context` shape without promoting it.

    The v0.2 exporter emits one project plus project-scoped collections and typed links.
    This bridge preserves each full source record inside the generic continuity proposal
    payload and adds a per-record SHA-256. It intentionally does not infer missing records
    or resolve relationships whose endpoints were omitted from the historical export.
    """

    raw = dict(context)
    version = raw.get("schema_version")
    if version != "0.2.0":
        raise ValueError(f"expected Second Brain schema_version '0.2.0', got {version!r}")

    project = raw.get("project")
    if not isinstance(project, Mapping):
        raise TypeError("Second Brain context project must be a mapping")

    entities: list[Json] = [_entity("project", "project", project)]
    for collection, entity_type in _COLLECTION_TYPES.items():
        values = raw.get(collection, []) or []
        if not isinstance(values, list):
            raise TypeError(f"Second Brain context {collection} must be a list")
        for record in values:
            if not isinstance(record, Mapping):
                raise TypeError(f"Second Brain {collection} entries must be mappings")
            entities.append(_entity(collection, entity_type, record))

    source_ids = [entity["source_id"] for entity in entities]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Second Brain context contains duplicate source record IDs")
    known_ids = set(source_ids)

    relationships: list[Json] = []
    links = raw.get("links", []) or []
    if not isinstance(links, list):
        raise TypeError("Second Brain context links must be a list")
    for link in links:
        if not isinstance(link, Mapping):
            raise TypeError("Second Brain link entries must be mappings")
        from_id = str(link.get("from_id") or "").strip()
        to_id = str(link.get("to_id") or "").strip()
        relation = str(link.get("relation") or "").strip()
        if not from_id or not to_id or not relation:
            raise ValueError("Second Brain links require from_id, relation, and to_id")
        if from_id not in known_ids or to_id not in known_ids:
            raise ValueError(
                "Second Brain context link endpoint was omitted from export: "
                f"{from_id!r} -> {to_id!r}"
            )
        relationships.append(
            {
                "source_id": from_id,
                "relation": relation,
                "target_id": to_id,
                "source_endpoint_type": str(link.get("from_type") or "").strip() or None,
                "target_endpoint_type": str(link.get("to_type") or "").strip() or None,
            }
        )

    artifacts: list[Json] = []
    for record in raw.get("library", []) or []:
        if not isinstance(record, Mapping):
            raise TypeError("Second Brain library entries must be mappings")
        artifact_id = _required_id(record, "library")
        checksum = str(record.get("checksum_sha256") or "").strip().lower()
        if not checksum:
            continue
        if not _SHA256_RE.fullmatch(checksum):
            raise ValueError(f"Second Brain library checksum is not SHA-256: {artifact_id}")
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "sha256": checksum,
                "media_type": str(record.get("media_type") or "").strip() or None,
                "logical_ref": str(record.get("location") or "").strip() or None,
            }
        )

    return {
        "source_system": SECOND_BRAIN_V02,
        "export_version": "0.2.0-context",
        "entities": entities,
        "relationships": relationships,
        "artifacts": artifacts,
    }


class SecondBrainContextAdapter:
    """Direct v0.2 context-export entry point over the canonical proposal adapter."""

    def __init__(self, store: CanonicalObjectStore):
        self.proposals = ContinuityProposalAdapter(store)

    def compile(
        self,
        context: Mapping[str, Any],
        *,
        artifact_payloads: Mapping[str, bytes] | None = None,
    ) -> Json:
        normalized = normalize_second_brain_v02_context(context)
        return self.proposals.compile(normalized, artifact_payloads=artifact_payloads)

    def ingest(
        self,
        context: Mapping[str, Any],
        *,
        source_ref: str,
        artifact_payloads: Mapping[str, bytes] | None = None,
    ) -> ContinuityProposalReceipt:
        normalized = normalize_second_brain_v02_context(context)
        return self.proposals.ingest(
            normalized,
            source_ref=source_ref,
            artifact_payloads=artifact_payloads,
        )
