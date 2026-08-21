from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from frost_core.gemini_provider import (
    DEFAULT_MODEL,
    GEMINI_API_BASE,
    GeminiConnectedEvidence,
    GeminiInteractionsProvider,
    GeminiProviderConfig,
    PrivacyClass,
)
from frost_core.providers import (
    ProviderAvailability,
    ProviderMaturity,
    ProviderRegistry,
    RoutingPolicy,
)


class FakeResponse:
    status = 200

    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _provider(opener=None) -> GeminiInteractionsProvider:
    kwargs = {
        "source_identity": "sha256:" + ("a" * 64),
        "key_getter": lambda: "secret-key",
    }
    if opener is not None:
        kwargs["opener"] = opener
    return GeminiInteractionsProvider(**kwargs)


def _completed(text: str = "ok") -> FakeResponse:
    return FakeResponse(
        {
            "id": "int-1",
            "model": DEFAULT_MODEL,
            "status": "completed",
            "steps": [
                {"type": "model_output", "content": [{"type": "text", "text": text}]}
            ],
            "usage": {"total_tokens": 2},
        }
    )


def test_host_record_is_not_connected_or_default_eligible(tmp_path: Path) -> None:
    record = _provider().provider_record()
    assert record.maturity == ProviderMaturity.HOST_VALIDATED
    assert record.availability == ProviderAvailability.UNKNOWN
    assert record.health == 0.0
    registry = ProviderRegistry(tmp_path / "providers.sqlite")
    registry.upsert(record)
    with pytest.raises(LookupError):
        registry.select(
            "model.generate.text",
            RoutingPolicy(minimum_maturity=ProviderMaturity.CONNECTED_VALIDATED),
        )


def test_connected_evidence_promotes_only_to_connected_validated() -> None:
    evidence = GeminiConnectedEvidence(
        passed=True,
        checked_at="2026-08-21T00:00:00+00:00",
        deployment_identity="gemini-api-key-scope:connected",
        latency_ms=123.0,
        response_sha256="b" * 64,
        status="completed",
    )
    record = _provider().provider_record(evidence)
    assert record.maturity == ProviderMaturity.CONNECTED_VALIDATED
    assert record.maturity < ProviderMaturity.PROMOTED
    assert record.availability == ProviderAvailability.AVAILABLE


def test_failed_probe_stays_host_validated_and_unavailable() -> None:
    evidence = GeminiConnectedEvidence(
        passed=False,
        checked_at="2026-08-21T00:00:00+00:00",
        deployment_identity="gemini-api-key-scope:unverified",
        latency_ms=None,
        response_sha256="",
        status="ERROR",
    )
    record = _provider().provider_record(evidence)
    assert record.maturity == ProviderMaturity.HOST_VALIDATED
    assert record.availability == ProviderAvailability.UNAVAILABLE


def test_sensitive_and_restricted_fail_before_network() -> None:
    called = False

    def opener(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("network should not be called")

    provider = _provider(opener)
    for privacy in (PrivacyClass.SENSITIVE, PrivacyClass.RESTRICTED):
        with pytest.raises(PermissionError):
            provider.infer("x", privacy=privacy)
    assert not called


def test_request_is_stable_v1_store_false_no_tools_and_low_is_valid() -> None:
    captured: dict[str, Any] = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _completed()

    result = _provider(opener).infer(
        "prompt", thinking_level="low", max_output_tokens=50
    )
    assert captured["url"] == GEMINI_API_BASE + "/interactions"
    assert captured["body"]["store"] is False
    assert "tools" not in captured["body"]
    assert captured["body"]["generation_config"]["tool_choice"] == "none"
    assert captured["body"]["generation_config"]["thinking_level"] == "low"
    assert result.classification == "UNVERIFIED_MODEL_OUTPUT"


def test_minimal_thinking_rejected_for_3_7_flash_before_network() -> None:
    provider = _provider(lambda *_a, **_k: pytest.fail("network called"))
    with pytest.raises(ValueError, match="thinking_level"):
        provider.infer("x", thinking_level="minimal")


def test_unknown_model_fails_before_network() -> None:
    provider = _provider(lambda *_a, **_k: pytest.fail("network called"))
    with pytest.raises(PermissionError):
        provider.infer("x", model="gemini-unknown")


def test_receipt_excludes_key_prompt_and_response_plaintext() -> None:
    result = _provider(lambda *_a, **_k: _completed("answer body")).infer("prompt body")
    receipt = json.dumps(result.receipt, sort_keys=True)
    assert "secret-key" not in receipt
    assert "prompt body" not in receipt
    assert "answer body" not in receipt
    assert result.receipt["classification"] == "UNVERIFIED_MODEL_OUTPUT"


def test_noncompleted_or_action_status_fails_closed() -> None:
    for status in ("requires_action", "failed", "incomplete", "queued"):
        provider = _provider(
            lambda *_a, status=status, **_k: FakeResponse(
                {"id": "int-1", "model": DEFAULT_MODEL, "status": status, "steps": []}
            )
        )
        with pytest.raises(RuntimeError):
            provider.infer("x")


def test_completed_without_text_fails_closed() -> None:
    provider = _provider(
        lambda *_a, **_k: FakeResponse(
            {"id": "int-1", "model": DEFAULT_MODEL, "status": "completed", "steps": []}
        )
    )
    with pytest.raises(RuntimeError, match="without text"):
        provider.infer("x")


def test_missing_key_fails_closed() -> None:
    provider = GeminiInteractionsProvider(
        source_identity="sha256:" + ("a" * 64), key_getter=lambda: None
    )
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        provider.infer("x")


def test_config_rejects_sensitive_remote_routing() -> None:
    config = GeminiProviderConfig(
        allowed_privacy=(PrivacyClass.PUBLIC, PrivacyClass.SENSITIVE)
    )
    with pytest.raises(ValueError, match="sensitive/restricted"):
        config.validate()


def test_config_rejects_nonstable_base() -> None:
    config = GeminiProviderConfig(api_base="https://example.invalid/v1")
    with pytest.raises(ValueError, match="stable v1"):
        config.validate()
