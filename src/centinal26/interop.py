from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from frost_core.federation import (
    AdapterKind,
    AdapterStatus,
    FederationCatalog,
    default_federation_catalog,
)

Json = dict[str, Any]

A2A_SPEC_VERSION = "1.0.0"
A2A_PROTOCOL_VERSION = "1.0"
MCP_PROTOCOL_VERSION = "2026-07-28"
ADAPTER_SCHEMA_VERSION = "automation-os.adapter/1.0"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "token_value",
        "api_key",
        "api_key_value",
        "credential",
        "credential_value",
        "private_key",
    }
)


class ProtocolFamily(StrEnum):
    A2A = "a2a"
    MCP = "mcp"


class AuthorizationState(StrEnum):
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    AUTHORIZED = "authorized"
    REVOKED = "revoked"
    EXPIRED = "expired"
    QUARANTINED = "quarantined"


class TrustTier(StrEnum):
    CANONICAL = "CANONICAL"
    COMPATIBLE_MODULE = "COMPATIBLE_MODULE"
    EXPERIMENTAL = "EXPERIMENTAL"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STALE = "stale"
    OFFLINE = "offline"
    QUARANTINED = "quarantined"


class TransportSemantics(StrEnum):
    STATELESS_REQUEST = "stateless_request"
    TASK_STATE = "task_state"
    APPLICATION_STATE = "application_state"


@dataclass(frozen=True)
class CapabilityDescriptor:
    capability_id: str
    canonical_operation: str
    protocol_operation: str
    required_scopes: tuple[str, ...]
    side_effects: str
    verification: str
    timeout_ms: int
    concurrency_limit: int


@dataclass(frozen=True)
class AuthProfile:
    auth_type: str
    credential_binding: str
    storage_policy: str
    requires_user_presence: bool
    delegation_allowed: bool
    scopes: tuple[str, ...]
    issuer: str | None = None
    audience: str | None = None


@dataclass(frozen=True)
class SessionState:
    state_id: str
    transport_semantics: TransportSemantics
    state_owner: str
    resumable: bool
    protocol_state: Json


@dataclass(frozen=True)
class HealthLease:
    lease_id: str
    subject_id: str
    issued_at: str
    expires_at: str
    heartbeat_interval_s: int
    grace_s: int
    status: HealthStatus
    last_seen_at: str
    renewal_counter: int


@dataclass(frozen=True)
class ArtifactIdentity:
    sha256: str | None
    source: str | None
    license: str | None


@dataclass(frozen=True)
class AdapterManifest:
    schema_version: str
    adapter_id: str
    adapter_version: str
    adapter_type: str
    protocol_family: ProtocolFamily
    protocol_version: str
    endpoint: str
    authorization_state: AuthorizationState
    trust_tier: TrustTier
    discovery: Json
    auth_profile: AuthProfile
    session_state: SessionState
    health_lease: HealthLease
    capabilities: tuple[CapabilityDescriptor, ...]
    artifact: ArtifactIdentity
    metadata: Json


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed.astimezone(UTC)


def _find_secret_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in _FORBIDDEN_SECRET_KEYS:
                hits.append(f"{path}.{key}")
            hits.extend(_find_secret_keys(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_find_secret_keys(child, f"{path}[{index}]"))
    return hits


def _expect_mapping(value: Any, name: str) -> Json:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return value


def _expect_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{name} must be an array of strings")
    return tuple(value)


def manifest_from_dict(raw: Json) -> AdapterManifest:
    protocol = _expect_mapping(raw["protocol"], "protocol")
    auth = _expect_mapping(raw["auth_profile"], "auth_profile")
    session = _expect_mapping(raw["session_state"], "session_state")
    health = _expect_mapping(raw["health_lease"], "health_lease")
    artifact = _expect_mapping(raw["artifact"], "artifact")
    capabilities_raw = raw["capabilities"]
    if not isinstance(capabilities_raw, list):
        raise TypeError("capabilities must be an array")

    capabilities = tuple(
        CapabilityDescriptor(
            capability_id=item["capability_id"],
            canonical_operation=item["canonical_operation"],
            protocol_operation=item["protocol_operation"],
            required_scopes=_expect_tuple(item.get("required_scopes", []), "required_scopes"),
            side_effects=item["side_effects"],
            verification=item["verification"],
            timeout_ms=item["timeout_ms"],
            concurrency_limit=item["concurrency_limit"],
        )
        for item in capabilities_raw
    )
    return AdapterManifest(
        schema_version=raw["schema_version"],
        adapter_id=raw["adapter_id"],
        adapter_version=raw["adapter_version"],
        adapter_type=raw["adapter_type"],
        protocol_family=ProtocolFamily(protocol["family"]),
        protocol_version=protocol["version"],
        endpoint=raw["endpoint"],
        authorization_state=AuthorizationState(raw["authorization_state"]),
        trust_tier=TrustTier(raw["trust_tier"]),
        discovery=_expect_mapping(raw["discovery"], "discovery"),
        auth_profile=AuthProfile(
            auth_type=auth["auth_type"],
            credential_binding=auth["credential_binding"],
            storage_policy=auth["storage_policy"],
            requires_user_presence=auth["requires_user_presence"],
            delegation_allowed=auth["delegation_allowed"],
            scopes=_expect_tuple(auth.get("scopes", []), "scopes"),
            issuer=auth.get("issuer"),
            audience=auth.get("audience"),
        ),
        session_state=SessionState(
            state_id=session["state_id"],
            transport_semantics=TransportSemantics(session["transport_semantics"]),
            state_owner=session["state_owner"],
            resumable=session["resumable"],
            protocol_state=_expect_mapping(session.get("protocol_state", {}), "protocol_state"),
        ),
        health_lease=HealthLease(
            lease_id=health["lease_id"],
            subject_id=health["subject_id"],
            issued_at=health["issued_at"],
            expires_at=health["expires_at"],
            heartbeat_interval_s=health["heartbeat_interval_s"],
            grace_s=health["grace_s"],
            status=HealthStatus(health["status"]),
            last_seen_at=health["last_seen_at"],
            renewal_counter=health["renewal_counter"],
        ),
        capabilities=capabilities,
        artifact=ArtifactIdentity(
            sha256=artifact.get("sha256"),
            source=artifact.get("source"),
            license=artifact.get("license"),
        ),
        metadata=_expect_mapping(raw.get("metadata", {}), "metadata"),
    )


def validate_manifest_dict(
    raw: Json,
    *,
    catalog: FederationCatalog | None = None,
    now: datetime | None = None,
) -> tuple[str, ...]:
    errors: list[str] = []
    secret_hits = _find_secret_keys(raw)
    if secret_hits:
        errors.append("inline credentials forbidden: " + ",".join(secret_hits))

    try:
        manifest = manifest_from_dict(raw)
    except (KeyError, TypeError, ValueError) as error:
        return tuple(errors + [f"manifest parse failed: {error}"])

    catalog = catalog or default_federation_catalog()
    now = (now or datetime.now(UTC)).astimezone(UTC)

    if manifest.schema_version != ADAPTER_SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if not _ID_RE.fullmatch(manifest.adapter_id):
        errors.append("invalid adapter_id")
    if manifest.adapter_id not in {"a2a", "mcp"}:
        errors.append("interop adapter_id must be a2a or mcp")
    if manifest.adapter_type not in {"declarative", "executable", "remote"}:
        errors.append("unsupported adapter_type")
    if not isinstance(manifest.endpoint, str) or not manifest.endpoint.strip():
        errors.append("endpoint is required")

    if manifest.protocol_family is ProtocolFamily.A2A:
        if manifest.protocol_version != A2A_PROTOCOL_VERSION:
            errors.append(f"a2a protocol must use wire version {A2A_PROTOCOL_VERSION}")
        if manifest.discovery.get("spec_release") != A2A_SPEC_VERSION:
            errors.append(f"a2a discovery must pin specification release {A2A_SPEC_VERSION}")
        card = manifest.discovery.get("agent_card_url")
        if not isinstance(card, str) or not card.startswith("https://"):
            errors.append("A2A requires an HTTPS Agent Card URL")
    else:
        if manifest.protocol_version != MCP_PROTOCOL_VERSION:
            errors.append(f"mcp protocol must be pinned to {MCP_PROTOCOL_VERSION}")
        if manifest.session_state.transport_semantics is not TransportSemantics.STATELESS_REQUEST:
            errors.append("MCP 2026-07-28 must use stateless_request transport semantics")
        protocol_state = manifest.session_state.protocol_state
        if "session_id" in protocol_state or "Mcp-Session-Id" in protocol_state:
            errors.append("legacy MCP session identifiers are forbidden")
        if protocol_state.get("initialize") is True or protocol_state.get("initialized") is True:
            errors.append("legacy MCP initialize handshake state is forbidden")

    if manifest.adapter_id != manifest.protocol_family.value:
        errors.append("adapter_id must match the protocol family")

    try:
        descriptor = catalog.get(manifest.adapter_id)
    except KeyError:
        errors.append("adapter is absent from the Automation OS federation catalog")
        descriptor = None

    if descriptor is not None and descriptor.kind is not AdapterKind.PROTOCOL:
        errors.append("interop adapter must map to a PROTOCOL catalog descriptor")

    if manifest.metadata.get("discovery_is_authority") is True:
        errors.append("discovery cannot be authorization authority")

    if manifest.adapter_type == "executable":
        digest = manifest.artifact.sha256
        if digest is None or _SHA256_RE.fullmatch(digest) is None:
            errors.append("executable adapter requires SHA-256 identity")

    if manifest.auth_profile.auth_type not in {
        "none",
        "api_key",
        "bearer",
        "oauth2",
        "oidc",
        "mtls",
        "local_identity",
    }:
        errors.append("unsupported auth_type")

    seen_capabilities: set[str] = set()
    granted_scopes = set(manifest.auth_profile.scopes)
    for capability in manifest.capabilities:
        if not _ID_RE.fullmatch(capability.capability_id) or "*" in capability.capability_id:
            errors.append(f"{capability.capability_id}: invalid capability_id")
        if capability.capability_id in seen_capabilities:
            errors.append(f"duplicate capability_id: {capability.capability_id}")
        seen_capabilities.add(capability.capability_id)

        if capability.side_effects not in {"none", "reversible", "irreversible"}:
            errors.append(f"{capability.capability_id}: invalid side_effects")
        if capability.verification not in {"required", "optional", "none"}:
            errors.append(f"{capability.capability_id}: invalid verification")
        if capability.side_effects == "irreversible" and capability.verification != "required":
            errors.append(f"{capability.capability_id}: irreversible capability requires verification")
        if not 1 <= capability.timeout_ms <= 3_600_000:
            errors.append(f"{capability.capability_id}: timeout_ms out of bounds")
        if not 1 <= capability.concurrency_limit <= 1024:
            errors.append(f"{capability.capability_id}: concurrency_limit out of bounds")
        if not set(capability.required_scopes).issubset(granted_scopes):
            errors.append(f"{capability.capability_id}: required scope is not granted")
        if descriptor is not None and capability.canonical_operation not in descriptor.operations:
            errors.append(
                f"{capability.capability_id}: canonical operation is not registered for {manifest.adapter_id}"
            )

    if any(capability.side_effects == "irreversible" for capability in manifest.capabilities):
        if manifest.adapter_type == "remote" and manifest.auth_profile.auth_type == "none":
            errors.append("remote irreversible capability cannot use auth_type=none")

    try:
        issued = _parse_datetime(manifest.health_lease.issued_at)
        expires = _parse_datetime(manifest.health_lease.expires_at)
        last_seen = _parse_datetime(manifest.health_lease.last_seen_at)
        if expires <= issued:
            errors.append("health lease expires_at must follow issued_at")
        if last_seen < issued:
            errors.append("health lease last_seen_at predates issued_at")
        if manifest.health_lease.status in {HealthStatus.HEALTHY, HealthStatus.DEGRADED}:
            grace_deadline = expires.timestamp() + manifest.health_lease.grace_s
            if now.timestamp() > grace_deadline:
                errors.append("health lease is expired beyond grace")
    except ValueError as error:
        errors.append(f"invalid health timestamp: {error}")

    return tuple(errors)


def is_route_eligible(
    raw: Json,
    *,
    catalog: FederationCatalog | None = None,
    now: datetime | None = None,
) -> bool:
    catalog = catalog or default_federation_catalog()
    if validate_manifest_dict(raw, catalog=catalog, now=now):
        return False
    manifest = manifest_from_dict(raw)
    if manifest.authorization_state is not AuthorizationState.AUTHORIZED:
        return False
    if manifest.trust_tier in {TrustTier.SUPERSEDED, TrustTier.REJECTED}:
        return False
    if manifest.health_lease.status not in {HealthStatus.HEALTHY, HealthStatus.DEGRADED}:
        return False
    descriptor = catalog.get(manifest.adapter_id)
    return descriptor.status not in {AdapterStatus.NOT_CONFIGURED, AdapterStatus.BLOCKED}


def select_route(
    manifests: list[Json],
    capability_id: str,
    *,
    catalog: FederationCatalog | None = None,
    now: datetime | None = None,
) -> Json | None:
    catalog = catalog or default_federation_catalog()
    candidates: list[tuple[tuple[int, int, str], Json]] = []
    trust_order = {
        TrustTier.CANONICAL: 0,
        TrustTier.COMPATIBLE_MODULE: 1,
        TrustTier.EXPERIMENTAL: 2,
    }
    for raw in manifests:
        if not is_route_eligible(raw, catalog=catalog, now=now):
            continue
        manifest = manifest_from_dict(raw)
        capability = next(
            (item for item in manifest.capabilities if item.capability_id == capability_id),
            None,
        )
        if capability is None:
            continue
        health_rank = 0 if manifest.health_lease.status is HealthStatus.HEALTHY else 1
        trust_rank = trust_order.get(manifest.trust_tier, 9)
        candidates.append(((health_rank, trust_rank, manifest.adapter_id), raw))
    candidates.sort(key=lambda item: item[0])
    return None if not candidates else candidates[0][1]
