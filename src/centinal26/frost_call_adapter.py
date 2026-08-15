from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from frost_core.federation import FederationCatalog

from .adapter_gateway import AdapterIngestResult, AdapterRequest, CanonicalAdapterGateway
from .event_state import EventStore

Json = dict[str, Any]
PROTOCOL_VERSION = "frost-call/1.0"
SUPPORTED_INGRESS_OPERATIONS = frozenset({"intent.submit"})
_RESERVED_CONSTRAINT_KEY = "_frost_call"


class FrostCallProtocolError(ValueError):
    """A frost-call envelope failed protocol validation before canonical ingestion."""


@dataclass(frozen=True)
class FrostCallEnvelope:
    protocol_version: str
    request_id: str
    operation: str
    parameters: Json
    caller: Json
    provenance: Json
    idempotency_key: str

    def as_dict(self) -> Json:
        return asdict(self)


@dataclass(frozen=True)
class FrostCallIngestResult:
    request_id: str
    idempotency_key: str
    envelope_sha256: str
    canonical: AdapterIngestResult

    def as_dict(self) -> Json:
        return {
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "envelope_sha256": self.envelope_sha256,
            "canonical": self.canonical.as_dict(),
        }


def _clean_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FrostCallProtocolError(f"{name} must be a non-empty string")
    return value.strip()


def _json_object(value: Any, *, name: str) -> Json:
    if not isinstance(value, dict):
        raise FrostCallProtocolError(f"{name} must be a JSON object")
    return value


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        message = "frost-call envelope must contain canonical JSON values"
        raise FrostCallProtocolError(message) from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def normalize_frost_call(raw: Any) -> FrostCallEnvelope:
    """Validate and normalize a frost-call/1.0 ingress envelope.

    This function establishes transport identity only. It grants no execution authority.
    """

    envelope = _json_object(raw, name="envelope")
    protocol_version = _clean_string(envelope.get("protocol_version"), name="protocol_version")
    if protocol_version != PROTOCOL_VERSION:
        raise FrostCallProtocolError(
            f"unsupported protocol_version: {protocol_version}; expected {PROTOCOL_VERSION}"
        )

    request_id = _clean_string(envelope.get("request_id"), name="request_id")
    operation = _clean_string(envelope.get("operation"), name="operation")
    if operation not in SUPPORTED_INGRESS_OPERATIONS:
        raise FrostCallProtocolError(
            f"unsupported ingress operation: {operation}; "
            f"supported={sorted(SUPPORTED_INGRESS_OPERATIONS)}"
        )

    parameters = _json_object(envelope.get("parameters", {}), name="parameters")
    caller = _json_object(envelope.get("caller", {}), name="caller")
    provenance = _json_object(envelope.get("provenance", {}), name="provenance")
    idempotency_key = _clean_string(
        envelope.get("idempotency_key", request_id),
        name="idempotency_key",
    )

    normalized = FrostCallEnvelope(
        protocol_version=protocol_version,
        request_id=request_id,
        operation=operation,
        parameters=json.loads(_canonical_json(parameters)),
        caller=json.loads(_canonical_json(caller)),
        provenance=json.loads(_canonical_json(provenance)),
        idempotency_key=idempotency_key,
    )
    _canonical_json(normalized.as_dict())
    return normalized


def to_adapter_request(envelope: FrostCallEnvelope) -> AdapterRequest:
    """Translate a validated frost-call envelope into the proposal-only canonical gateway."""

    parameters = envelope.parameters
    capability = _clean_string(parameters.get("capability"), name="parameters.capability")
    payload = _json_object(parameters.get("payload"), name="parameters.payload")
    constraints = _json_object(parameters.get("constraints", {}), name="parameters.constraints")
    if _RESERVED_CONSTRAINT_KEY in constraints:
        raise FrostCallProtocolError(
            f"parameters.constraints.{_RESERVED_CONSTRAINT_KEY} is reserved by the protocol adapter"
        )

    objective = parameters.get("objective")
    if objective is not None:
        objective = _clean_string(objective, name="parameters.objective")

    actor = parameters.get("actor")
    if actor is not None:
        actor = _clean_string(actor, name="parameters.actor")
    elif isinstance(envelope.caller.get("id"), str) and envelope.caller["id"].strip():
        actor = envelope.caller["id"].strip()
    elif isinstance(envelope.caller.get("type"), str) and envelope.caller["type"].strip():
        actor = f"frost-call:{envelope.caller['type'].strip()}"

    transport_metadata: Json = {
        "protocol_version": envelope.protocol_version,
        "request_id": envelope.request_id,
        "idempotency_key": envelope.idempotency_key,
        "caller": envelope.caller,
        "provenance": envelope.provenance,
    }
    source = parameters.get("source")
    if source is not None:
        transport_metadata["source"] = _json_object(source, name="parameters.source")

    canonical_constraints = dict(constraints)
    canonical_constraints[_RESERVED_CONSTRAINT_KEY] = transport_metadata

    return AdapterRequest(
        adapter_id="frost-call",
        external_id=envelope.idempotency_key,
        capability=capability,
        payload=json.loads(_canonical_json(payload)),
        constraints=json.loads(_canonical_json(canonical_constraints)),
        objective=objective,
        actor=actor,
    )


def ingest_frost_call(
    store: EventStore,
    raw: Any,
    *,
    catalog: FederationCatalog | None = None,
) -> FrostCallIngestResult:
    """Normalize frost-call/1.0 into Centinal26 without bypassing canonical gates."""

    envelope = normalize_frost_call(raw)
    envelope_sha256 = _sha256(envelope.as_dict())
    canonical = CanonicalAdapterGateway(store, catalog).ingest(to_adapter_request(envelope))
    return FrostCallIngestResult(
        request_id=envelope.request_id,
        idempotency_key=envelope.idempotency_key,
        envelope_sha256=envelope_sha256,
        canonical=canonical,
    )
