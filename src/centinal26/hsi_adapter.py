from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

Json = dict[str, Any]
PROTOCOL_VERSION = "hsi/1.0"
SUPPORTED_OPERATIONS = frozenset(
    {"hsi.status", "hsi.identify", "hsi.run", "hsi.verify", "hsi.export"}
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class HSIProtocolError(ValueError):
    """The HSI typed-capability request failed validation before canonical ingestion."""


@dataclass(frozen=True)
class HSIRequest:
    protocol_version: str
    request_id: str
    operation: str
    parameters: Json
    caller: Json
    provenance: Json
    idempotency_key: str

    def as_dict(self) -> Json:
        return asdict(self)


def _clean(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HSIProtocolError(f"{name} must be a non-empty string")
    return value.strip()


def _object(value: Any, *, name: str) -> Json:
    if not isinstance(value, dict):
        raise HSIProtocolError(f"{name} must be a JSON object")
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
        raise HSIProtocolError("HSI request must contain canonical JSON values") from error


def _sha(value: str, *, name: str) -> str:
    value = _clean(value, name=name).lower()
    if not _SHA256.fullmatch(value):
        raise HSIProtocolError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _reject_execution_surface(parameters: Json) -> None:
    prohibited = {"command", "shell", "argv", "packages", "script", "executable"}
    overlap = prohibited.intersection(parameters)
    if overlap:
        raise HSIProtocolError(
            "HSI transport accepts typed references only; prohibited execution fields: "
            + ", ".join(sorted(overlap))
        )


def _normalize_parameters(operation: str, raw: Json) -> Json:
    _reject_execution_surface(raw)
    if operation == "hsi.status":
        allowed = {"backend"}
        extra = set(raw) - allowed
        if extra:
            raise HSIProtocolError(f"hsi.status unsupported parameters: {sorted(extra)}")
        backend = str(raw.get("backend", "canonical")).strip() or "canonical"
        return {"backend": backend}

    if operation in {"hsi.identify", "hsi.run"}:
        allowed = {"spec_ref", "spec_sha256", "backend", "runs", "seed", "objective"}
        extra = set(raw) - allowed
        if extra:
            raise HSIProtocolError(f"{operation} unsupported parameters: {sorted(extra)}")
        spec_ref = _clean(raw.get("spec_ref"), name="parameters.spec_ref")
        spec_sha256 = _sha(raw.get("spec_sha256"), name="parameters.spec_sha256")
        backend = str(raw.get("backend", "canonical-finite")).strip() or "canonical-finite"
        if backend not in {"canonical-finite", "canonical-baseline", "branch2-v1.5"}:
            raise HSIProtocolError("unsupported HSI backend")
        out: Json = {"spec_ref": spec_ref, "spec_sha256": spec_sha256, "backend": backend}
        if operation == "hsi.run":
            runs = raw.get("runs", 1)
            if not isinstance(runs, int) or isinstance(runs, bool) or not 1 <= runs <= 1_000_000:
                raise HSIProtocolError("parameters.runs must be an integer in [1,1000000]")
            out["runs"] = runs
            if "seed" in raw:
                seed = raw["seed"]
                if not isinstance(seed, int) or isinstance(seed, bool):
                    raise HSIProtocolError("parameters.seed must be an integer")
                out["seed"] = seed
            if "objective" in raw:
                objective = _clean(raw["objective"], name="parameters.objective")
                if objective not in {"nevsi", "mi_estimand", "mi_system", "structural"}:
                    raise HSIProtocolError("unsupported HSI objective")
                out["objective"] = objective
        elif any(key in raw for key in ("runs", "seed", "objective")):
            raise HSIProtocolError("run-only parameters supplied to hsi.identify")
        return out

    if operation == "hsi.verify":
        allowed = {"artifact_ref", "artifact_sha256", "verification_type"}
        extra = set(raw) - allowed
        if extra:
            raise HSIProtocolError(f"hsi.verify unsupported parameters: {sorted(extra)}")
        verification_type = str(raw.get("verification_type", "evidence_chain")).strip()
        if verification_type not in {"evidence_chain", "manifest", "structural_certificate"}:
            raise HSIProtocolError("unsupported verification_type")
        return {
            "artifact_ref": _clean(raw.get("artifact_ref"), name="parameters.artifact_ref"),
            "artifact_sha256": _sha(raw.get("artifact_sha256"), name="parameters.artifact_sha256"),
            "verification_type": verification_type,
        }

    if operation == "hsi.export":
        allowed = {"artifact_ref", "artifact_sha256", "format"}
        extra = set(raw) - allowed
        if extra:
            raise HSIProtocolError(f"hsi.export unsupported parameters: {sorted(extra)}")
        fmt = str(raw.get("format", "json")).strip().lower()
        if fmt not in {"json", "jsonl", "csv", "zip"}:
            raise HSIProtocolError("unsupported export format")
        return {
            "artifact_ref": _clean(raw.get("artifact_ref"), name="parameters.artifact_ref"),
            "artifact_sha256": _sha(raw.get("artifact_sha256"), name="parameters.artifact_sha256"),
            "format": fmt,
        }
    raise HSIProtocolError(f"unsupported HSI operation: {operation}")


def normalize_hsi_request(raw: Any) -> HSIRequest:
    envelope = _object(raw, name="request")
    protocol_version = _clean(envelope.get("protocol_version"), name="protocol_version")
    if protocol_version != PROTOCOL_VERSION:
        raise HSIProtocolError(
            f"unsupported protocol_version: {protocol_version}; expected {PROTOCOL_VERSION}"
        )
    request_id = _clean(envelope.get("request_id"), name="request_id")
    operation = _clean(envelope.get("operation"), name="operation")
    if operation not in SUPPORTED_OPERATIONS:
        raise HSIProtocolError(f"unsupported HSI operation: {operation}")
    raw_parameters = _object(envelope.get("parameters", {}), name="parameters")
    parameters = _normalize_parameters(operation, raw_parameters)
    caller = _object(envelope.get("caller", {}), name="caller")
    provenance = _object(envelope.get("provenance", {}), name="provenance")
    idempotency_key = _clean(envelope.get("idempotency_key", request_id), name="idempotency_key")
    result = HSIRequest(
        protocol_version=protocol_version,
        request_id=request_id,
        operation=operation,
        parameters=json.loads(_canonical_json(parameters)),
        caller=json.loads(_canonical_json(caller)),
        provenance=json.loads(_canonical_json(provenance)),
        idempotency_key=idempotency_key,
    )
    _canonical_json(result.as_dict())
    return result


def to_frost_call_envelope(request: HSIRequest) -> Json:
    """Translate HSI into existing proposal-only frost-call ingress.

    This translation grants no execution authority. The hsi.* capability must still
    exist in the normal capability registry and pass authorization, execution,
    verification, evidence, and terminal-state gates.
    """
    return {
        "protocol_version": "frost-call/1.0",
        "request_id": request.request_id,
        "operation": "intent.submit",
        "idempotency_key": request.idempotency_key,
        "parameters": {
            "capability": request.operation,
            "payload": request.parameters,
            "constraints": {
                "hsi_protocol": request.protocol_version,
                "typed_capability": True,
                "no_arbitrary_shell": True,
            },
            "objective": f"typed hidden-system identification operation {request.operation}",
            "source": {"protocol": request.protocol_version},
        },
        "caller": request.caller,
        "provenance": request.provenance,
    }


def request_sha256(request: HSIRequest) -> str:
    return hashlib.sha256(_canonical_json(request.as_dict()).encode()).hexdigest()


def ingest_hsi_request(store: Any, raw: Any, *, catalog: Any = None) -> Any:
    """Enter HSI work through the existing proposal-only canonical gateway."""
    from .frost_call_adapter import ingest_frost_call

    request = normalize_hsi_request(raw)
    return ingest_frost_call(store, to_frost_call_envelope(request), catalog=catalog)
