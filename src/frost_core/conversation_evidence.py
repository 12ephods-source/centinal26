from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .object_store import CanonicalObjectStore

Json = dict[str, Any]
SECONDARY_RECONCILIATION = "SECONDARY_RECONCILIATION"


@dataclass(frozen=True)
class ConversationEvidenceReceipt:
    reconciliation_id: str
    conversation_id: str
    project_candidate_id: str | None
    claim_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    decision_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    reusable_component_ids: tuple[str, ...]


class ConversationEvidenceIngestor:
    """Import conversation-reconciliation output as evidence, never authority.

    The ingestor deliberately writes into :class:`CanonicalObjectStore` instead of
    maintaining a second ledger. Project assignments remain candidates, contradictions
    remain unresolved, and no alias/current pointer is advanced automatically.
    """

    def __init__(self, store: CanonicalObjectStore):
        self.store = store

    def ingest(
        self,
        conversation_state: Mapping[str, Any],
        *,
        source_ref: str,
        file_inventory: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
        reusable_components: Sequence[Mapping[str, Any]] | None = None,
    ) -> ConversationEvidenceReceipt:
        source_ref = str(source_ref).strip()
        if not source_ref:
            raise ValueError("source_ref is required")

        state = dict(conversation_state)
        audit_version = str(state.get("audit_version") or "").strip()
        if not audit_version:
            raise ValueError("conversation_state.audit_version is required")

        conversation_id = self._conversation_id(state)
        if not conversation_id:
            raise ValueError("conversation id is required")

        root_payload: Json = {
            "audit_version": audit_version,
            "conversation_id": conversation_id,
            "conversation_title": state.get("conversation_title"),
            "conversation_summary": state.get("conversation_summary"),
            "conversation_goal": state.get("conversation_goal"),
            "project_goal": state.get("project_goal"),
            "account_goal": state.get("account_goal"),
            "epistemic_caveats": list(state.get("epistemic_caveats") or []),
        }
        reconciliation_id = self._put(
            "conversation_reconciliation",
            root_payload,
            source_ref=source_ref,
        )

        project_candidate_id = self._ingest_project_candidate(
            reconciliation_id,
            conversation_id,
            state.get("project"),
            source_ref=source_ref,
        )

        claim_ids = self._ingest_values(
            reconciliation_id,
            conversation_id,
            "conversation_claim",
            "HAS_CLAIM",
            state.get("accomplishments") or state.get("claims") or [],
            source_ref=source_ref,
        )
        contradiction_ids = self._ingest_values(
            reconciliation_id,
            conversation_id,
            "conversation_contradiction",
            "HAS_CONTRADICTION",
            state.get("contradictions") or [],
            source_ref=source_ref,
            forced_status="UNRESOLVED",
        )
        decision_ids = self._ingest_values(
            reconciliation_id,
            conversation_id,
            "conversation_decision",
            "HAS_DECISION",
            state.get("persistent_decisions") or [],
            source_ref=source_ref,
        )

        artifacts = self._normalize_inventory(file_inventory)
        artifact_ids = self._ingest_values(
            reconciliation_id,
            conversation_id,
            "conversation_artifact_reference",
            "REFERENCES_ARTIFACT",
            artifacts,
            source_ref=source_ref,
        )
        reusable_component_ids = self._ingest_values(
            reconciliation_id,
            conversation_id,
            "conversation_reusable_candidate",
            "HAS_REUSABLE_CANDIDATE",
            reusable_components or state.get("reusable_components") or [],
            source_ref=source_ref,
            forced_status="CANDIDATE",
        )

        return ConversationEvidenceReceipt(
            reconciliation_id=reconciliation_id,
            conversation_id=conversation_id,
            project_candidate_id=project_candidate_id,
            claim_ids=claim_ids,
            contradiction_ids=contradiction_ids,
            decision_ids=decision_ids,
            artifact_ids=artifact_ids,
            reusable_component_ids=reusable_component_ids,
        )

    def _put(self, kind: str, payload: Json, *, source_ref: str) -> str:
        return self.store.put(
            kind,
            payload,
            source_type="chatgpt_reconciliation",
            source_ref=source_ref,
            evidence_class=SECONDARY_RECONCILIATION,
        )

    def _ingest_project_candidate(
        self,
        reconciliation_id: str,
        conversation_id: str,
        project: Any,
        *,
        source_ref: str,
    ) -> str | None:
        if not isinstance(project, Mapping):
            return None
        name = str(project.get("name") or "").strip()
        if not name:
            return None
        payload: Json = {
            "conversation_id": conversation_id,
            "name": name,
            "confidence": project.get("confidence"),
            "alternatives": list(project.get("alternatives") or []),
            "status": "CANDIDATE",
        }
        object_id = self._put(
            "project_assignment_candidate",
            payload,
            source_ref=source_ref,
        )
        self.store.link(reconciliation_id, "HAS_PROJECT_CANDIDATE", object_id)
        return object_id

    def _ingest_values(
        self,
        reconciliation_id: str,
        conversation_id: str,
        kind: str,
        relation: str,
        values: Sequence[Any],
        *,
        source_ref: str,
        forced_status: str | None = None,
    ) -> tuple[str, ...]:
        ids: list[str] = []
        for value in values:
            payload: Json = {
                "conversation_id": conversation_id,
                "value": self._jsonable(value),
            }
            if forced_status is not None:
                payload["status"] = forced_status
            object_id = self._put(kind, payload, source_ref=source_ref)
            self.store.link(reconciliation_id, relation, object_id)
            ids.append(object_id)
        return tuple(ids)

    @staticmethod
    def _conversation_id(state: Mapping[str, Any]) -> str:
        direct = str(state.get("conversation_id") or "").strip()
        if direct:
            return direct
        protocol = state.get("protocol")
        if isinstance(protocol, Mapping):
            return str(protocol.get("conversation_id") or "").strip()
        return ""

    @staticmethod
    def _normalize_inventory(
        inventory: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None,
    ) -> list[Mapping[str, Any]]:
        if inventory is None:
            return []
        if isinstance(inventory, Mapping):
            values = inventory.get("files") or []
            return [item for item in values if isinstance(item, Mapping)]
        return [item for item in inventory if isinstance(item, Mapping)]

    @classmethod
    def _jsonable(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(key): cls._jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._jsonable(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)
