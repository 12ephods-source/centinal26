from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from frost_core.federation import AdapterStatus, FederationCatalog, default_federation_catalog

from .event_state import EventStore, derive_ready_tasks, rebuild_state

Json = dict[str, Any]
CANONICAL_ADAPTER_IDS = frozenset({"aaard", "base44", "discord", "fras", "hermes"})
_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9_.-]+")


class AdapterRequestConflict(ValueError):
    """A stable adapter request identity was reused with different immutable content."""


@dataclass(frozen=True)
class AdapterRequest:
    adapter_id: str
    external_id: str
    capability: str
    payload: Json
    constraints: Json = field(default_factory=dict)
    objective: str | None = None
    actor: str | None = None


@dataclass(frozen=True)
class AdapterIngestResult:
    adapter_id: str
    external_id: str
    request_id: str
    task_id: str
    request_sha256: str
    duplicate: bool
    events_appended: int

    def as_dict(self) -> Json:
        return asdict(self)


def _clean(value: str, *, name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{name} must not be empty")
    return cleaned


def _safe_token(value: str) -> str:
    token = _SAFE_TOKEN.sub("-", value.strip()).strip("-")
    return token[:48] or "adapter"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _request_body(request: AdapterRequest) -> Json:
    adapter_id = _clean(request.adapter_id, name="adapter_id")
    external_id = _clean(request.external_id, name="external_id")
    capability = _clean(request.capability, name="capability")
    if not isinstance(request.payload, dict):
        raise TypeError("payload must be a JSON object")
    if not isinstance(request.constraints, dict):
        raise TypeError("constraints must be a JSON object")
    objective = request.objective.strip() if isinstance(request.objective, str) else None
    if request.objective is not None and not objective:
        raise ValueError("objective must not be empty when provided")
    actor = request.actor.strip() if isinstance(request.actor, str) else None
    if request.actor is not None and not actor:
        raise ValueError("actor must not be empty when provided")
    body: Json = {
        "adapter_id": adapter_id,
        "external_id": external_id,
        "capability": capability,
        "payload": request.payload,
        "constraints": request.constraints,
        "objective": objective,
        "actor": actor,
    }
    return json.loads(_canonical_json(body))


def _request_sha256(body: Json) -> str:
    return hashlib.sha256(_canonical_json(body).encode()).hexdigest()


def _stable_suffix(adapter_id: str, external_id: str) -> str:
    digest = hashlib.sha256(f"{adapter_id}\0{external_id}".encode()).hexdigest()
    return digest[:24]


class CanonicalAdapterGateway:
    """Normalize external adapters into the canonical event-sourced task graph.

    The gateway is intentionally proposal-only. It creates no grants and performs no
    execution. A request becomes a canonical task that must still pass the normal
    Centinal26 authorization, capability, verification, evidence, and state gates.
    """

    def __init__(
        self,
        store: EventStore,
        catalog: FederationCatalog | None = None,
    ) -> None:
        self.store = store
        self.catalog = catalog or default_federation_catalog()

    def ingest(self, request: AdapterRequest) -> AdapterIngestResult:
        if not self.store.verify_chain():
            raise ValueError("refusing adapter ingestion because the event chain is invalid")

        body = _request_body(request)
        adapter_id = body["adapter_id"]
        external_id = body["external_id"]
        capability = body["capability"]

        if adapter_id not in CANONICAL_ADAPTER_IDS:
            raise ValueError(f"unsupported canonical adapter: {adapter_id}")
        descriptor = self.catalog.get(adapter_id)
        if descriptor.status is AdapterStatus.BLOCKED:
            raise PermissionError(f"adapter is blocked: {adapter_id}")
        if "intent.submit" not in descriptor.operations:
            raise ValueError(f"adapter is not registered for intent.submit: {adapter_id}")

        digest = _request_sha256(body)
        suffix = _stable_suffix(adapter_id, external_id)
        request_id = f"adapter-request:{_safe_token(adapter_id)}:{suffix}"
        task_id = f"task:adapter:{_safe_token(adapter_id)}:{suffix}"
        start_count = self.store.count()

        state = rebuild_state(self.store.events())
        existing_source = state.sources.get(request_id)
        if existing_source is not None:
            if existing_source.get("request_sha256") != digest:
                raise AdapterRequestConflict(
                    f"{adapter_id}:{external_id} already exists with different content"
                )
        else:
            self.store.append(
                "SOURCE_INGESTED",
                {
                    "source_id": request_id,
                    "kind": "adapter-request",
                    "adapter_id": adapter_id,
                    "external_id": external_id,
                    "request_sha256": digest,
                    "capability": capability,
                    "catalog_status": descriptor.status.value,
                    "authority": "proposal_only",
                    "request": body,
                },
                entity_id=request_id,
            )

        state = rebuild_state(self.store.events())
        existing_task = state.tasks.get(task_id)
        if existing_task is not None:
            if (
                existing_task.get("request_sha256") != digest
                or existing_task.get("source_id") != request_id
            ):
                raise AdapterRequestConflict(
                    f"{adapter_id}:{external_id} task identity conflicts with canonical state"
                )
        else:
            objective = body["objective"] or f"{adapter_id} request for {capability}"
            self.store.append(
                "TASK_CREATED",
                {
                    "task_id": task_id,
                    "source_id": request_id,
                    "objective": objective,
                    "capability": capability,
                    "input": body["payload"],
                    "constraints": body["constraints"],
                    "adapter_id": adapter_id,
                    "external_id": external_id,
                    "request_sha256": digest,
                    "actor": body["actor"] or f"adapter:{adapter_id}",
                    "authority": "authorization_required",
                },
                entity_id=task_id,
            )

        state = rebuild_state(self.store.events())
        if task_id not in derive_ready_tasks(state):
            task = state.tasks[task_id]
            if task.get("status") not in {
                "AUTHORIZED",
                "RUNNING",
                "EXECUTED",
                "VERIFIED",
                "COMPLETE",
                "FAILED",
                "VERIFICATION_FAILED",
            }:
                message = f"canonicalized adapter task is unexpectedly not ready: {task_id}"
                raise RuntimeError(message)

        return AdapterIngestResult(
            adapter_id=adapter_id,
            external_id=external_id,
            request_id=request_id,
            task_id=task_id,
            request_sha256=digest,
            duplicate=self.store.count() == start_count,
            events_appended=self.store.count() - start_count,
        )
