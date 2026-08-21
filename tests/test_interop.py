from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

from centinal26.interop import (
    A2A_PROTOCOL_VERSION,
    A2A_SPEC_VERSION,
    MCP_PROTOCOL_VERSION,
    is_route_eligible,
    select_route,
    validate_manifest_dict,
)
from frost_core.federation import AdapterStatus, default_federation_catalog


def _now() -> datetime:
    return datetime(2026, 8, 21, 17, 0, tzinfo=UTC)


def manifest(adapter_id: str) -> dict:
    now = _now()
    if adapter_id == "a2a":
        protocol_version = A2A_PROTOCOL_VERSION
        discovery = {
            "agent_card_url": "https://agent.example/.well-known/agent-card.json",
            "spec_release": A2A_SPEC_VERSION,
        }
        operation = "agent.message"
        protocol_operation = "message/send"
        transport = "task_state"
        protocol_state = {"task_ref": "task-1"}
    else:
        protocol_version = MCP_PROTOCOL_VERSION
        discovery = {"server_discovery": True}
        operation = "tools.call"
        protocol_operation = "tools/call"
        transport = "stateless_request"
        protocol_state = {}

    return {
        "schema_version": "automation-os.adapter/1.0",
        "adapter_id": adapter_id,
        "adapter_version": "1.0.0",
        "adapter_type": "remote",
        "protocol": {"family": adapter_id, "version": protocol_version},
        "endpoint": f"https://{adapter_id}.example/api",
        "authorization_state": "authorized",
        "trust_tier": "COMPATIBLE_MODULE",
        "discovery": discovery,
        "auth_profile": {
            "auth_type": "oauth2",
            "credential_binding": "issuer_bound",
            "storage_policy": "external_secret_store",
            "requires_user_presence": False,
            "delegation_allowed": False,
            "scopes": ["invoke"],
            "issuer": "https://issuer.example",
            "audience": f"https://{adapter_id}.example",
        },
        "session_state": {
            "state_id": f"{adapter_id}-state",
            "transport_semantics": transport,
            "state_owner": "remote_peer" if adapter_id == "a2a" else "none",
            "resumable": adapter_id == "a2a",
            "protocol_state": protocol_state,
        },
        "health_lease": {
            "lease_id": f"{adapter_id}-lease",
            "subject_id": adapter_id,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=10)).isoformat(),
            "heartbeat_interval_s": 30,
            "grace_s": 60,
            "status": "healthy",
            "last_seen_at": now.isoformat(),
            "renewal_counter": 1,
        },
        "capabilities": [
            {
                "capability_id": f"{adapter_id}.invoke",
                "canonical_operation": operation,
                "protocol_operation": protocol_operation,
                "required_scopes": ["invoke"],
                "side_effects": "reversible",
                "verification": "required",
                "timeout_ms": 30_000,
                "concurrency_limit": 4,
            }
        ],
        "artifact": {"sha256": None, "source": None, "license": None},
        "metadata": {"discovery_is_authority": False},
    }


def test_current_a2a_spec_release_uses_major_minor_wire_version() -> None:
    assert A2A_SPEC_VERSION == "1.0.0"
    assert A2A_PROTOCOL_VERSION == "1.0"
    raw = manifest("a2a")
    assert validate_manifest_dict(raw, now=_now()) == ()


def test_a2a_patch_version_is_rejected_on_wire() -> None:
    raw = manifest("a2a")
    raw["protocol"]["version"] = "1.0.0"
    errors = validate_manifest_dict(raw, now=_now())
    assert any("wire version 1.0" in error for error in errors)


def test_a2a_requires_https_agent_card_and_spec_pin() -> None:
    raw = manifest("a2a")
    raw["discovery"]["agent_card_url"] = "http://agent.example/card"
    raw["discovery"]["spec_release"] = "0.3.0"
    errors = validate_manifest_dict(raw, now=_now())
    assert any("HTTPS Agent Card" in error for error in errors)
    assert any("specification release 1.0.0" in error for error in errors)


def test_current_mcp_is_stateless_and_rejects_legacy_session_state() -> None:
    raw = manifest("mcp")
    assert validate_manifest_dict(raw, now=_now()) == ()
    legacy = deepcopy(raw)
    legacy["session_state"]["transport_semantics"] = "application_state"
    legacy["session_state"]["protocol_state"] = {"Mcp-Session-Id": "legacy", "initialize": True}
    errors = validate_manifest_dict(legacy, now=_now())
    assert any("stateless_request" in error for error in errors)
    assert any("session identifiers" in error for error in errors)
    assert any("initialize handshake" in error for error in errors)


def test_inline_secrets_fail_closed_anywhere_in_manifest() -> None:
    raw = manifest("mcp")
    raw["metadata"]["nested"] = {"api_key": "secret-value"}
    errors = validate_manifest_dict(raw, now=_now())
    assert any("inline credentials forbidden" in error for error in errors)


def test_wildcard_and_unregistered_operations_fail_closed() -> None:
    raw = manifest("mcp")
    raw["capabilities"][0]["capability_id"] = "mcp.*"
    raw["capabilities"][0]["canonical_operation"] = "shell.exec"
    errors = validate_manifest_dict(raw, now=_now())
    assert any("invalid capability_id" in error for error in errors)
    assert any("canonical operation is not registered" in error for error in errors)


def test_missing_scope_and_unverified_irreversible_capability_fail_closed() -> None:
    raw = manifest("mcp")
    raw["capabilities"][0]["required_scopes"] = ["admin"]
    raw["capabilities"][0]["side_effects"] = "irreversible"
    raw["capabilities"][0]["verification"] = "optional"
    errors = validate_manifest_dict(raw, now=_now())
    assert any("required scope is not granted" in error for error in errors)
    assert any("irreversible capability requires verification" in error for error in errors)


def test_expired_health_lease_is_invalid() -> None:
    raw = manifest("mcp")
    raw["health_lease"]["expires_at"] = (_now() - timedelta(minutes=5)).isoformat()
    errors = validate_manifest_dict(raw, now=_now())
    assert any("expired beyond grace" in error for error in errors)


def test_discovery_does_not_create_route_eligibility() -> None:
    catalog = default_federation_catalog()
    for adapter_id in ("a2a", "mcp"):
        raw = manifest(adapter_id)
        assert validate_manifest_dict(raw, catalog=catalog, now=_now()) == ()
        assert catalog.get(adapter_id).status is AdapterStatus.NOT_CONFIGURED
        assert is_route_eligible(raw, catalog=catalog, now=_now()) is False


def test_authorized_manifest_only_routes_after_catalog_status_is_enabled() -> None:
    catalog = default_federation_catalog()
    raw = manifest("mcp")
    assert is_route_eligible(raw, catalog=catalog, now=_now()) is False
    catalog.mark_status("mcp", AdapterStatus.HOST_VALIDATED)
    assert is_route_eligible(raw, catalog=catalog, now=_now()) is True


def test_revoked_or_quarantined_manifest_remains_unroutable() -> None:
    catalog = default_federation_catalog()
    catalog.mark_status("a2a", AdapterStatus.HOST_VALIDATED)
    revoked = manifest("a2a")
    revoked["authorization_state"] = "revoked"
    assert is_route_eligible(revoked, catalog=catalog, now=_now()) is False
    quarantined = manifest("a2a")
    quarantined["health_lease"]["status"] = "quarantined"
    assert is_route_eligible(quarantined, catalog=catalog, now=_now()) is False


def test_select_route_prefers_healthy_then_trust_without_bypassing_catalog() -> None:
    catalog = default_federation_catalog()
    a2a = manifest("a2a")
    mcp = manifest("mcp")
    a2a["capabilities"][0]["capability_id"] = "shared.invoke"
    mcp["capabilities"][0]["capability_id"] = "shared.invoke"
    assert select_route([a2a, mcp], "shared.invoke", catalog=catalog, now=_now()) is None

    catalog.mark_status("a2a", AdapterStatus.HOST_VALIDATED)
    catalog.mark_status("mcp", AdapterStatus.HOST_VALIDATED)
    a2a["health_lease"]["status"] = "degraded"
    mcp["trust_tier"] = "EXPERIMENTAL"
    selected = select_route([a2a, mcp], "shared.invoke", catalog=catalog, now=_now())
    assert selected is mcp
