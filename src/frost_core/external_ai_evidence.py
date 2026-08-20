from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .object_store import CanonicalObjectStore

EXTERNAL_AI_LOCATOR = "EXTERNAL_AI_LOCATOR"
EXTERNAL_AI_PRIMARY_SOURCE = "EXTERNAL_AI_PRIMARY_SOURCE"
_ALLOWED_STATUS = {"ACQUIRED", "PARTIAL", "UNAVAILABLE"}
_ALLOWED_COMPLETENESS = {"COMPLETE", "PARTIAL", "UNKNOWN"}


@dataclass(frozen=True)
class ExternalAIReceipt:
    source_id: str
    transcript_id: str | None
    acquisition_status: str
    completeness: str
    analysis_ready: bool


class ExternalAIEvidenceIngestor:
    """Ingest external-AI conversations as source evidence, never authority.

    This boundary deliberately performs no network retrieval, claim extraction,
    project promotion, contradiction resolution, capability enablement, or action
    execution. A source locator may be recorded even when its content is unavailable.
    Transcript-derived analysis must occur downstream only after actual acquisition.
    """

    def __init__(self, store: CanonicalObjectStore):
        self.store = store

    def ingest(
        self,
        *,
        platform: str,
        source_ref: str,
        acquisition_status: str,
        completeness: str = "UNKNOWN",
        conversation_id: str | None = None,
        transcript_text: str | None = None,
        transcript_sha256: str | None = None,
        attachments: Sequence[Mapping[str, Any]] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExternalAIReceipt:
        platform = str(platform).strip().lower()
        source_ref = str(source_ref).strip()
        status = str(acquisition_status).strip().upper()
        completeness = str(completeness).strip().upper()
        conversation_id = str(conversation_id or "").strip() or None

        if not platform:
            raise ValueError("platform is required")
        if not source_ref:
            raise ValueError("source_ref is required")
        if status not in _ALLOWED_STATUS:
            raise ValueError(f"unsupported acquisition_status: {status}")
        if completeness not in _ALLOWED_COMPLETENESS:
            raise ValueError(f"unsupported completeness: {completeness}")

        normalized_attachments = [dict(item) for item in attachments or []]
        source_payload = {
            "platform": platform,
            "source_ref": source_ref,
            "conversation_id": conversation_id,
            "acquisition_status": status,
            "completeness": completeness,
            "attachments": normalized_attachments,
            "metadata": dict(metadata or {}),
        }

        source_id = self.store.put(
            "external_ai_source",
            source_payload,
            source_type=f"external_ai:{platform}",
            source_ref=source_ref,
            evidence_class=EXTERNAL_AI_LOCATOR,
        )

        if status == "UNAVAILABLE":
            if transcript_text is not None or transcript_sha256 is not None:
                raise ValueError("UNAVAILABLE source may not include transcript content or hash")
            if completeness != "UNKNOWN":
                raise ValueError("UNAVAILABLE source completeness must be UNKNOWN")
            return ExternalAIReceipt(
                source_id=source_id,
                transcript_id=None,
                acquisition_status=status,
                completeness=completeness,
                analysis_ready=False,
            )

        if transcript_text is None:
            raise ValueError(f"{status} source requires transcript_text")
        if transcript_sha256 is None:
            raise ValueError(f"{status} source requires transcript_sha256")
        if status == "ACQUIRED" and completeness == "UNKNOWN":
            raise ValueError("ACQUIRED source completeness must be COMPLETE or PARTIAL")
        if status == "PARTIAL" and completeness != "PARTIAL":
            raise ValueError("PARTIAL source completeness must be PARTIAL")

        actual_sha256 = hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()
        expected_sha256 = str(transcript_sha256).strip().lower()
        if actual_sha256 != expected_sha256:
            raise ValueError("transcript_sha256 does not match transcript_text")

        transcript_payload = {
            "platform": platform,
            "source_id": source_id,
            "conversation_id": conversation_id,
            "text": transcript_text,
            "sha256": actual_sha256,
            "completeness": completeness,
        }
        transcript_id = self.store.put(
            "external_ai_transcript",
            transcript_payload,
            source_type=f"external_ai:{platform}",
            source_ref=source_ref,
            evidence_class=EXTERNAL_AI_PRIMARY_SOURCE,
        )
        self.store.link(source_id, "HAS_TRANSCRIPT", transcript_id)

        return ExternalAIReceipt(
            source_id=source_id,
            transcript_id=transcript_id,
            acquisition_status=status,
            completeness=completeness,
            analysis_ready=True,
        )
