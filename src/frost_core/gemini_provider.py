from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .providers import ProviderAvailability, ProviderMaturity, ProviderRecord

Json = dict[str, Any]
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1"
GEMINI_PROVIDER_ID = "gemini-interactions-v1"
DEFAULT_MODEL = "gemini-3.7-flash"
ALLOWED_MODELS = (DEFAULT_MODEL,)
THINKING_LEVELS = ("low", "medium", "high")


class PrivacyClass(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class GeminiProviderConfig:
    model: str = DEFAULT_MODEL
    allowed_models: tuple[str, ...] = ALLOWED_MODELS
    allowed_privacy: tuple[PrivacyClass, ...] = (
        PrivacyClass.PUBLIC,
        PrivacyClass.INTERNAL,
    )
    api_base: str = GEMINI_API_BASE
    timeout_seconds: int = 60
    max_prompt_bytes: int = 262_144
    max_output_tokens: int = 65_536
    thinking_level: str = "medium"

    def validate(self) -> None:
        if self.api_base != GEMINI_API_BASE:
            raise ValueError("Gemini provider is pinned to the stable v1 API")
        if self.model not in self.allowed_models:
            raise ValueError("default model must be allowlisted")
        if not self.allowed_models or any(model not in ALLOWED_MODELS for model in self.allowed_models):
            raise ValueError("only approved stable Gemini models may be allowlisted")
        if any(value not in (PrivacyClass.PUBLIC, PrivacyClass.INTERNAL) for value in self.allowed_privacy):
            raise ValueError("remote sensitive/restricted routing is prohibited")
        if not 1 <= self.timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")
        if not 1 <= self.max_prompt_bytes <= 4 * 1024 * 1024:
            raise ValueError("max_prompt_bytes is out of bounds")
        if not 1 <= self.max_output_tokens <= 65_536:
            raise ValueError("max_output_tokens is out of bounds")
        if self.thinking_level not in THINKING_LEVELS:
            raise ValueError("invalid thinking_level")


@dataclass(frozen=True)
class GeminiConnectedEvidence:
    passed: bool
    checked_at: str
    deployment_identity: str
    latency_ms: float | None
    response_sha256: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class GeminiInferenceResult:
    text: str
    model: str
    status: str
    usage: Json
    receipt: Json
    classification: str = "UNVERIFIED_MODEL_OUTPUT"


@dataclass
class GeminiInteractionsProvider:
    """Bounded remote-model adapter; provider output is never semantic verification."""

    source_identity: str
    config: GeminiProviderConfig = field(default_factory=GeminiProviderConfig)
    key_getter: Callable[[], str | None] = field(
        default=lambda: os.environ.get("GEMINI_API_KEY")
    )
    opener: Callable[..., Any] = field(default=urllib.request.urlopen)

    def __post_init__(self) -> None:
        self.config.validate()
        if not self.source_identity.strip():
            raise ValueError("source_identity is required")

    def provider_record(
        self, evidence: GeminiConnectedEvidence | None = None
    ) -> ProviderRecord:
        connected = bool(evidence and evidence.passed)
        failed_probe = bool(evidence and not evidence.passed)
        availability = ProviderAvailability.UNKNOWN
        maturity = ProviderMaturity.HOST_VALIDATED
        health = 0.0
        latency_ms = None
        deployment_identity = None
        if connected:
            availability = ProviderAvailability.AVAILABLE
            maturity = ProviderMaturity.CONNECTED_VALIDATED
            health = 1.0
            latency_ms = evidence.latency_ms
            deployment_identity = evidence.deployment_identity
        elif failed_probe:
            availability = ProviderAvailability.UNAVAILABLE
        return ProviderRecord(
            provider_id=GEMINI_PROVIDER_ID,
            provider_type="remote_model",
            capabilities=("model.generate.text", "model.reason", "model.code.assist"),
            maturity=maturity,
            availability=availability,
            deployment_identity=deployment_identity,
            source_identity=self.source_identity,
            health=health,
            latency_ms=latency_ms,
            cost_rank=40,
            limitations=(
                "public_or_internal_only",
                "no_tool_execution",
                "no_plaintext_audit_persistence",
                "output_requires_independent_verification",
            ),
            metadata={
                "provider": "gemini",
                "api": "interactions-v1",
                "api_base": self.config.api_base,
                "default_model": self.config.model,
                "allowed_models": list(self.config.allowed_models),
                "request_store": False,
                "tool_execution": False,
                "output_classification": "UNVERIFIED_MODEL_OUTPUT",
            },
        )

    def infer(
        self,
        prompt: str,
        *,
        privacy: PrivacyClass = PrivacyClass.INTERNAL,
        model: str | None = None,
        thinking_level: str | None = None,
        max_output_tokens: int | None = None,
        system_instruction: str | None = None,
    ) -> GeminiInferenceResult:
        selected_model = model or self.config.model
        selected_thinking = thinking_level or self.config.thinking_level
        selected_max = max_output_tokens or self.config.max_output_tokens
        if privacy not in self.config.allowed_privacy:
            raise PermissionError(f"remote inference denied for privacy class: {privacy.value}")
        if selected_model not in self.config.allowed_models:
            raise PermissionError(f"model not allowlisted: {selected_model}")
        if selected_thinking not in THINKING_LEVELS:
            raise ValueError("invalid thinking_level")
        if not 1 <= selected_max <= self.config.max_output_tokens:
            raise ValueError("max_output_tokens exceeds configured bound")
        prompt_bytes = prompt.encode("utf-8")
        if not prompt_bytes:
            raise ValueError("prompt must not be empty")
        if len(prompt_bytes) > self.config.max_prompt_bytes:
            raise ValueError("prompt exceeds configured byte limit")
        key = (self.key_getter() or "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        body: Json = {
            "model": selected_model,
            "input": prompt,
            "store": False,
            "generation_config": {
                "thinking_level": selected_thinking,
                "max_output_tokens": selected_max,
                "tool_choice": "none",
            },
        }
        if system_instruction:
            body["system_instruction"] = system_instruction
        request = urllib.request.Request(
            f"{self.config.api_base}/interactions",
            data=_canonical_bytes(body),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key,
                "User-Agent": "centinal26-frost-core/gemini",
            },
        )
        started = time.monotonic()
        try:
            with self.opener(request, timeout=self.config.timeout_seconds) as response:
                response_bytes = response.read()
                http_status = int(getattr(response, "status", 200))
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            redacted = raw.decode("utf-8", errors="replace").replace(key, "<redacted>")
            raise RuntimeError(f"Gemini HTTP {exc.code}: {redacted[:500]}") from None
        elapsed_ms = int((time.monotonic() - started) * 1000)
        payload = json.loads(response_bytes.decode("utf-8"))
        status = str(payload.get("status", "unknown"))
        if status == "requires_action":
            raise RuntimeError("Gemini requested action; provider is fail-closed")
        if status != "completed":
            raise RuntimeError(f"Gemini interaction did not complete: {status}")
        text = _extract_text(payload)
        receipt = {
            "provider": "gemini",
            "api": "interactions-v1",
            "http_status": http_status,
            "status": status,
            "model": str(payload.get("model", selected_model)),
            "interaction_id_sha256": _sha256_text(str(payload.get("id", ""))),
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "prompt_bytes": len(prompt_bytes),
            "response_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "response_bytes": len(text.encode("utf-8")),
            "elapsed_ms": elapsed_ms,
            "usage": payload.get("usage", {}),
            "store": False,
            "tool_execution": False,
            "classification": "UNVERIFIED_MODEL_OUTPUT",
        }
        return GeminiInferenceResult(
            text=text,
            model=str(payload.get("model", selected_model)),
            status=status,
            usage=dict(payload.get("usage", {})),
            receipt=receipt,
        )

    def connected_probe(self) -> GeminiConnectedEvidence:
        started = time.monotonic()
        try:
            result = self.infer(
                "Reply with exactly: GEMINI_OK",
                privacy=PrivacyClass.PUBLIC,
                thinking_level="low",
                max_output_tokens=16,
            )
            passed = result.text.strip() == "GEMINI_OK"
            detail = "exact probe response" if passed else "unexpected probe response"
            response_sha256 = str(result.receipt["response_sha256"])
        except (OSError, RuntimeError, ValueError) as exc:
            return GeminiConnectedEvidence(
                passed=False,
                checked_at=_utc_now(),
                deployment_identity="gemini-api-key-scope:unverified",
                latency_ms=None,
                response_sha256="",
                status="ERROR",
                detail=f"{type(exc).__name__}: {exc}",
            )
        return GeminiConnectedEvidence(
            passed=passed,
            checked_at=_utc_now(),
            deployment_identity=(
                "gemini-api-key-scope:connected" if passed else "gemini-api-key-scope:unverified"
            ),
            latency_ms=float(int((time.monotonic() - started) * 1000)),
            response_sha256=response_sha256,
            status=result.status,
            detail=detail,
        )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _extract_text(payload: Json) -> str:
    chunks: list[str] = []
    for step in payload.get("steps", []) or []:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for item in step.get("content", []) or []:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    text = "".join(chunks)
    if not text:
        raise RuntimeError("Gemini completed without text model output")
    return text


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
