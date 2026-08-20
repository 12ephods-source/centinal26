from __future__ import annotations

from datetime import UTC, datetime

from centinal26.interop import is_route_eligible, select_route, validate_manifest_dict
from frost_core.federation import (
    AdapterDescriptor,
    AdapterKind,
    AdapterStatus,
    FederationCatalog,
)

NOW = datetime.fromisoformat("2026-08-19T22:36:00-06:00").astimezone(UTC)


def catalog() -> FederationCatalog:
    return FederationCatalog(
        (
            AdapterDescriptor(
                "a2a",
                AdapterKind.PROTOCOL,
                ("agent.message",),
                status=AdapterStatus.HOST_VALIDATED,
            ),
            AdapterDescriptor(
                "mcp",
                AdapterKind.PROTOCOL,
                ("tools.list", "tools.call"),
                status=AdapterStatus.HOST_VALIDATED,
            ),
        )
    )


def manifest(adapter_id: str = "mcp") -> dict:
    common = {
        "schema_version": "wazoo26.adapter/0.2",
        "adapter_id": adapter_id,
        "adapter_version": "0.2.0",
        "adapter_type": "remote",
        "authorization_state": "authorized",
        "trust_tier": "EXPERIMENTAL",
        "artifact": {"sha256": None, "source": "remote", "license": None},
        "metadata": {"discovery_is_authority": False},
    }
    if adapter_id == "mcp":
        return {
            **common,
            "protocol": {"family": "mcp", "version": "2026-07-28"},
            "endpoint": "https://example.invalid/mcp",
            "discovery": {"method": "server/discover"},
            "auth_profile": {
                "auth_type": "oauth2",
                "credential_binding": "issuer_bound",
                "storage_policy": "external_secret_store",
                "requires_user_presence": False,
                "delegation_allowed": False,
                "scopes": ["tools.call"],
                "issuer": "https://auth.example.invalid",
                "audience": "https://example.invalid/mcp",
            },
            "session_state": {
                "state_id": "mcp-stateless",
                "transport_semantics": "stateless_request",
                "state_owner": "none",
                "resumable": False,
                "protocol_state": {},
            },
            "health_lease": {
                "lease_id": "lease-mcp",
                "subject_id": "mcp",
                "issued_at": "2026-08-19T22:00:00-06:00",
                "expires_at": "2026-08-20T00:00:00-06:00",
                "heartbeat_interval_s": 60,
                "grace_s": 30,
                "status": "healthy",
                "last_seen_at": "2026-08-19T22:35:00-06:00",
                "renewal_counter": 3,
            },
            "capabilities": [
                {
                    "capability_id": "tool.search",
                    "canonical_operation": "tools.call",
                    "protocol_operation": "tools/call:search",
                    "required_scopes": ["tools.call"],
                    "side_effects": "none",
                    "verification": "required",
                    "timeout_ms": 30_000,
                    "concurrency_limit": 4,
                }
            ],
        }
    return {
        **common,
        "protocol": {"family": "a2a", "version": "1.0.0"},
        "endpoint": "https://agent.example.invalid/a2a",
        "discovery": {
            "method": "agent_card",
            "agent_card_url": "https://agent.example.invalid/.well-known/agent-card.json",
        },
        "auth_profile": {
            "auth_type": "oauth2",
            "credential_binding": "issuer_bound",
            "storage_policy": "external_secret_store",
            "requires_user_presence": False,
            "delegation_allowed": False,
            "scopes": ["agent.invoke"],
            "issuer": "https://auth.example.invalid",
            "audience": "https://agent.example.invalid/a2a",
        },
        "session_state": {
            "state_id": "a2a-task",
            "transport_semantics": "task_state",
            "state_owner": "remote_peer",
            "resumable": True,
            "protocol_state": {},
        },
        "health_lease": {
            "lease_id": "lease-a2a",
            "subject_id": "a2a",
            "issued_at": "2026-08-19T22:00:00-06:00",
            "expires_at": "2026-08-20T00:00:00-06:00",
            "heartbeat_interval_s": 60,
            "grace_s": 30,
            "status": "healthy",
            "last_seen_at": "2026-08-19T22:35:00-06:00",
            "renewal_counter": 3,
        },
        "capabilities": [
            {
                "capability_id": "agent.research.delegate",
                "canonical_operation": "agent.message",
                "protocol_operation": "message/send",
                "required_scopes": ["agent.invoke"],
                "side_effects": "none",
                "verification": "required",
                "timeout_ms": 120_000,
                "concurrency_limit": 2,
            }
        ],
    }


def test_mcp_manifest_passes() -> None:
    assert validate_manifest_dict(manifest(), catalog=catalog(), now=NOW) == ()


def test_a2a_manifest_passes() -> None:
    assert validate_manifest_dict(manifest("a2a"), catalog=catalog(), now=NOW) == ()


def test_default_catalog_is_not_route_eligible() -> None:
    assert not is_route_eligible(manifest(), now=NOW)


def test_host_validated_catalog_is_route_eligible() -> None:
    assert is_route_eligible(manifest(), catalog=catalog(), now=NOW)


def test_discovery_cannot_authorize() -> None:
    candidate = manifest()
    candidate["metadata"]["discovery_is_authority"] = True
    assert "discovery cannot be authorization authority" in validate_manifest_dict(
        candidate, catalog=catalog(), now=NOW
    )


def test_inline_secret_is_rejected() -> None:
    candidate = manifest()
    candidate["auth_profile"]["token_value"] = "do-not-store-this"
    assert any(
        "inline credentials forbidden" in error
        for error in validate_manifest_dict(candidate, catalog=catalog(), now=NOW)
    )


def test_mcp_legacy_session_is_rejected() -> None:
    candidate = manifest()
    candidate["session_state"]["transport_semantics"] = "task_state"
    candidate["session_state"]["protocol_state"]["Mcp-Session-Id"] = "legacy"
    errors = validate_manifest_dict(candidate, catalog=catalog(), now=NOW)
    assert any("stateless_request" in error for error in errors)
    assert any("legacy MCP session identifiers" in error for error in errors)


def test_protocol_version_is_pinned() -> None:
    candidate = manifest("a2a")
    candidate["protocol"]["version"] = "0.3.0"
    assert any(
        "must be pinned to 1.0.0" in error
        for error in validate_manifest_dict(candidate, catalog=catalog(), now=NOW)
    )


def test_wildcard_capability_is_rejected() -> None:
    candidate = manifest()
    candidate["capabilities"][0]["capability_id"] = "tool.*"
    assert any(
        "invalid capability_id" in error
        for error in validate_manifest_dict(candidate, catalog=catalog(), now=NOW)
    )


def test_missing_scope_is_rejected() -> None:
    candidate = manifest()
    candidate["auth_profile"]["scopes"] = []
    assert any(
        "required scope is not granted" in error
        for error in validate_manifest_dict(candidate, catalog=catalog(), now=NOW)
    )


def test_unregistered_canonical_operation_is_rejected() -> None:
    candidate = manifest()
    candidate["capabilities"][0]["canonical_operation"] = "shell.exec"
    assert any(
        "canonical operation is not registered" in error
        for error in validate_manifest_dict(candidate, catalog=catalog(), now=NOW)
    )


def test_irreversible_requires_verification() -> None:
    candidate = manifest()
    candidate["capabilities"][0]["side_effects"] = "irreversible"
    candidate["capabilities"][0]["verification"] = "optional"
    assert any(
        "irreversible capability requires verification" in error
        for error in validate_manifest_dict(candidate, catalog=catalog(), now=NOW)
    )


def test_revoked_authorization_is_not_route_eligible() -> None:
    candidate = manifest()
    candidate["authorization_state"] = "revoked"
    assert not is_route_eligible(candidate, catalog=catalog(), now=NOW)


def test_stale_health_is_not_route_eligible() -> None:
    candidate = manifest()
    candidate["health_lease"]["status"] = "stale"
    assert not is_route_eligible(candidate, catalog=catalog(), now=NOW)


def test_expired_health_is_rejected() -> None:
    candidate = manifest()
    candidate["health_lease"]["expires_at"] = "2026-08-19T22:01:00-06:00"
    assert "health lease is expired beyond grace" in validate_manifest_dict(
        candidate, catalog=catalog(), now=NOW
    )


def test_route_selects_matching_capability() -> None:
    result = select_route([manifest(), manifest("a2a")], "tool.search", catalog=catalog(), now=NOW)
    assert result is not None
    assert result["adapter_id"] == "mcp"


def test_route_rejects_unmatched_capability() -> None:
    assert select_route([manifest()], "agent.research.delegate", catalog=catalog(), now=NOW) is None


def test_executable_requires_sha256_identity() -> None:
    candidate = manifest()
    candidate["adapter_type"] = "executable"
    assert "executable adapter requires SHA-256 identity" in validate_manifest_dict(
        candidate, catalog=catalog(), now=NOW
    )
