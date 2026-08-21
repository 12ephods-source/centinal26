from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .object_store import CanonicalObjectStore

Json = dict[str, Any]
MIGRATION_PROPOSAL = "MIGRATION_PROPOSAL"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _stable_source_identity(source_system: str, entity_type: str, source_id: str) -> str:
    return _digest(
        {
            "source_system": source_system,
            "entity_type": entity_type,
            "source_id": source_id,
        }
    )


@dataclass(frozen=True)
class ContinuityProposalReceipt:
    proposal_object_id: str
    source_digest: str
    entity_count: int
    relationship_count: int
    artifact_count: int


class ContinuityProposalAdapter:
    """Compile historical continuity records into one immutable proposal object.

    This adapter intentionally has no execution, alias/current-pointer, contradiction-
    resolution, or epistemic-promotion API. It validates the complete export before
    making a single content-addressed store write, which makes failed validation
    non-mutating and successful ingestion idempotent.
    """

    SCHEMA = "frost.automation.continuity_migration_proposal.v1"

    def __init__(self, store: CanonicalObjectStore):
        self.store = store

    def ingest(
        self,
        export: Mapping[str, Any],
        *,
        source_ref: str,
        artifact_payloads: Mapping[str, bytes] | None = None,
    ) -> ContinuityProposalReceipt:
        source_ref = str(source_ref).strip()
        if not source_ref:
            raise ValueError("source_ref is required")

        proposal = self.compile(export, artifact_payloads=artifact_payloads)
        proposal_object_id = self.store.put(
            "continuity_migration_proposal",
            proposal,
            source_type="historical_continuity_migration",
            source_ref=source_ref,
            evidence_class=MIGRATION_PROPOSAL,
        )
        return ContinuityProposalReceipt(
            proposal_object_id=proposal_object_id,
            source_digest=proposal["source_digest"],
            entity_count=len(proposal["entities"]),
            relationship_count=len(proposal["relationships"]),
            artifact_count=len(proposal["artifacts"]),
        )

    def compile(
        self,
        export: Mapping[str, Any],
        *,
        artifact_payloads: Mapping[str, bytes] | None = None,
    ) -> Json:
        raw = dict(export)
        source_system = str(raw.get("source_system") or "").strip()
        export_version = str(raw.get("export_version") or "").strip()
        if not source_system:
            raise ValueError("source_system is required")
        if not export_version:
            raise ValueError("export_version is required")

        entities = self._normalize_entities(source_system, raw.get("entities") or [])
        known_ids = {entity["source_id"] for entity in entities}
        relationships = self._normalize_relationships(raw.get("relationships") or [], known_ids)
        artifacts = self._normalize_artifacts(
            raw.get("artifacts") or [],
            artifact_payloads=artifact_payloads or {},
        )

        source_digest = _digest(
            {
                "source_system": source_system,
                "export_version": export_version,
                "entities": entities,
                "relationships": relationships,
                "artifacts": artifacts,
            }
        )
        return {
            "schema": self.SCHEMA,
            "status": "PROPOSAL_ONLY",
            "source_system": source_system,
            "export_version": export_version,
            "source_digest": source_digest,
            "authority": {
                "canonical_target": "Centinal26 canonical continuity layer",
                "machine_continuation": "automation/PROJECT_STATE.json",
                "execution_authority": False,
                "automatic_epistemic_promotion": False,
                "automatic_contradiction_resolution": False,
                "alias_or_current_pointer_update": False,
            },
            "entities": entities,
            "relationships": relationships,
            "artifacts": artifacts,
        }

    @classmethod
    def _normalize_entities(cls, source_system: str, values: Sequence[Any]) -> list[Json]:
        if isinstance(values, (str, bytes)):
            raise TypeError("entities must be a sequence of mappings")
        result: list[Json] = []
        seen: set[str] = set()
        for raw in values:
            if not isinstance(raw, Mapping):
                raise TypeError("each entity must be a mapping")
            source_id = str(raw.get("source_id") or "").strip()
            entity_type = str(raw.get("entity_type") or "").strip()
            if not source_id or not entity_type:
                raise ValueError("entity source_id and entity_type are required")
            if source_id in seen:
                raise ValueError(f"duplicate entity source_id: {source_id}")
            seen.add(source_id)
            epistemic_status = raw.get("epistemic_status")
            if epistemic_status is not None:
                epistemic_status = str(epistemic_status).strip()
                if not epistemic_status:
                    raise ValueError(f"empty epistemic_status for {source_id}")
            revision_parent = raw.get("revision_parent")
            if revision_parent is not None:
                revision_parent = str(revision_parent).strip() or None
            result.append(
                {
                    "stable_id": _stable_source_identity(source_system, entity_type, source_id),
                    "source_id": source_id,
                    "entity_type": entity_type,
                    "epistemic_status": epistemic_status,
                    "revision_parent": revision_parent,
                    "payload": cls._jsonable(raw.get("payload") or {}),
                }
            )
        result.sort(key=lambda item: item["stable_id"])
        source_ids = {item["source_id"] for item in result}
        for item in result:
            parent = item["revision_parent"]
            if parent is not None and parent not in source_ids:
                raise ValueError(
                    f"revision_parent {parent!r} for {item['source_id']!r} is not present"
                )
        return result

    @staticmethod
    def _normalize_relationships(values: Sequence[Any], known_ids: set[str]) -> list[Json]:
        if isinstance(values, (str, bytes)):
            raise TypeError("relationships must be a sequence of mappings")
        result: list[Json] = []
        seen: set[tuple[str, str, str]] = set()
        for raw in values:
            if not isinstance(raw, Mapping):
                raise TypeError("each relationship must be a mapping")
            source_id = str(raw.get("source_id") or "").strip()
            relation = str(raw.get("relation") or "").strip()
            target_id = str(raw.get("target_id") or "").strip()
            if not source_id or not relation or not target_id:
                raise ValueError("relationship source_id, relation, and target_id are required")
            if source_id not in known_ids or target_id not in known_ids:
                raise ValueError(
                    f"relationship endpoints must exist in export: {source_id!r} -> {target_id!r}"
                )
            key = (source_id, relation, target_id)
            if key in seen:
                continue
            seen.add(key)
            relationship: Json = {
                "source_id": source_id,
                "relation": relation,
                "target_id": target_id,
            }
            source_endpoint_type = str(raw.get("source_endpoint_type") or "").strip()
            target_endpoint_type = str(raw.get("target_endpoint_type") or "").strip()
            if source_endpoint_type:
                relationship["source_endpoint_type"] = source_endpoint_type
            if target_endpoint_type:
                relationship["target_endpoint_type"] = target_endpoint_type
            result.append(relationship)
        result.sort(key=lambda item: (item["source_id"], item["relation"], item["target_id"]))
        return result

    @staticmethod
    def _normalize_artifacts(
        values: Sequence[Any], *, artifact_payloads: Mapping[str, bytes]
    ) -> list[Json]:
        if isinstance(values, (str, bytes)):
            raise TypeError("artifacts must be a sequence of mappings")
        result: list[Json] = []
        seen: set[str] = set()
        for raw in values:
            if not isinstance(raw, Mapping):
                raise TypeError("each artifact must be a mapping")
            artifact_id = str(raw.get("artifact_id") or "").strip()
            sha256 = str(raw.get("sha256") or "").strip().lower()
            if not artifact_id:
                raise ValueError("artifact_id is required")
            if artifact_id in seen:
                raise ValueError(f"duplicate artifact_id: {artifact_id}")
            seen.add(artifact_id)
            if not _SHA256_RE.fullmatch(sha256):
                raise ValueError(f"artifact {artifact_id!r} requires lowercase SHA-256")

            verification = "HASH_PRESERVED_BYTES_NOT_PROVIDED"
            if artifact_id in artifact_payloads:
                payload = artifact_payloads[artifact_id]
                if not isinstance(payload, bytes):
                    raise TypeError(f"artifact payload for {artifact_id!r} must be bytes")
                actual = hashlib.sha256(payload).hexdigest()
                if actual != sha256:
                    raise ValueError(
                        f"artifact SHA-256 mismatch for {artifact_id!r}: expected {sha256}, got {actual}"
                    )
                verification = "SHA256_VERIFIED_FROM_SUPPLIED_BYTES"

            result.append(
                {
                    "artifact_id": artifact_id,
                    "sha256": sha256,
                    "verification": verification,
                    "media_type": str(raw.get("media_type") or "").strip() or None,
                    "logical_ref": str(raw.get("logical_ref") or "").strip() or None,
                }
            )
        result.sort(key=lambda item: item["artifact_id"])
        return result

    @classmethod
    def _jsonable(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(key): cls._jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._jsonable(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)
