from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AdapterKind(StrEnum):
    CLOUD_AI = "CLOUD_AI"
    LOCAL_AI = "LOCAL_AI"
    AGENT_FRAMEWORK = "AGENT_FRAMEWORK"
    PROTOCOL = "PROTOCOL"
    MESSAGING = "MESSAGING"
    EXECUTION_PROVIDER = "EXECUTION_PROVIDER"
    CONTROL_PLANE = "CONTROL_PLANE"
    SOFTWARE_CREATION = "SOFTWARE_CREATION"


class AdapterStatus(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DISCOVERED = "DISCOVERED"
    HOST_VALIDATED = "HOST_VALIDATED"
    CONNECTED_VALIDATED = "CONNECTED_VALIDATED"
    DEVICE_VALIDATED = "DEVICE_VALIDATED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    kind: AdapterKind
    operations: tuple[str, ...]
    status: AdapterStatus = AdapterStatus.NOT_CONFIGURED
    auth_required: bool = True
    local_only: bool = False
    notes: tuple[str, ...] = ()


class FederationCatalog:
    """Typed discovery catalog for HERMES and provider-neutral orchestration.

    Catalog membership is descriptive, not authorization. `NOT_CONFIGURED` entries are
    planned integration surfaces and must not be treated as usable providers.
    """

    def __init__(self, descriptors: tuple[AdapterDescriptor, ...] = ()):
        self._descriptors = {descriptor.adapter_id: descriptor for descriptor in descriptors}

    def register(self, descriptor: AdapterDescriptor) -> None:
        if not descriptor.adapter_id.strip() or not descriptor.operations:
            raise ValueError("adapter_id and operations are required")
        self._descriptors[descriptor.adapter_id] = descriptor

    def get(self, adapter_id: str) -> AdapterDescriptor:
        try:
            return self._descriptors[adapter_id]
        except KeyError as error:
            raise KeyError(f"unknown adapter: {adapter_id}") from error

    def discover(
        self,
        *,
        kind: AdapterKind | None = None,
        operation: str | None = None,
        minimum_status: AdapterStatus | None = None,
    ) -> tuple[AdapterDescriptor, ...]:
        status_order = {
            AdapterStatus.NOT_CONFIGURED: 0,
            AdapterStatus.DISCOVERED: 1,
            AdapterStatus.HOST_VALIDATED: 2,
            AdapterStatus.CONNECTED_VALIDATED: 3,
            AdapterStatus.DEVICE_VALIDATED: 4,
            AdapterStatus.BLOCKED: -1,
        }
        results = []
        for descriptor in self._descriptors.values():
            if kind is not None and descriptor.kind != kind:
                continue
            if operation is not None and operation not in descriptor.operations:
                continue
            if (
                minimum_status is not None
                and status_order[descriptor.status] < status_order[minimum_status]
            ):
                continue
            results.append(descriptor)
        return tuple(sorted(results, key=lambda item: item.adapter_id))

    def mark_status(self, adapter_id: str, status: AdapterStatus) -> AdapterDescriptor:
        current = self.get(adapter_id)
        updated = AdapterDescriptor(
            adapter_id=current.adapter_id,
            kind=current.kind,
            operations=current.operations,
            status=status,
            auth_required=current.auth_required,
            local_only=current.local_only,
            notes=current.notes,
        )
        self._descriptors[adapter_id] = updated
        return updated

    def all(self) -> tuple[AdapterDescriptor, ...]:
        return tuple(sorted(self._descriptors.values(), key=lambda item: item.adapter_id))


def default_federation_catalog() -> FederationCatalog:
    descriptors = (
        AdapterDescriptor("openai", AdapterKind.CLOUD_AI, ("model.invoke",)),
        AdapterDescriptor("anthropic", AdapterKind.CLOUD_AI, ("model.invoke",)),
        AdapterDescriptor("gemini", AdapterKind.CLOUD_AI, ("model.invoke",)),
        AdapterDescriptor("xai", AdapterKind.CLOUD_AI, ("model.invoke",)),
        AdapterDescriptor("mistral", AdapterKind.CLOUD_AI, ("model.invoke",)),
        AdapterDescriptor("cohere", AdapterKind.CLOUD_AI, ("model.invoke",)),
        AdapterDescriptor("openrouter", AdapterKind.CLOUD_AI, ("model.invoke",)),
        AdapterDescriptor("llama.cpp", AdapterKind.LOCAL_AI, ("model.invoke",), local_only=True),
        AdapterDescriptor("ollama", AdapterKind.LOCAL_AI, ("model.invoke",), local_only=True),
        AdapterDescriptor("lm-studio", AdapterKind.LOCAL_AI, ("model.invoke",), local_only=True),
        AdapterDescriptor("langgraph", AdapterKind.AGENT_FRAMEWORK, ("agent.invoke",)),
        AdapterDescriptor("crewai", AdapterKind.AGENT_FRAMEWORK, ("agent.invoke",)),
        AdapterDescriptor("autogen", AdapterKind.AGENT_FRAMEWORK, ("agent.invoke",)),
        AdapterDescriptor("google-adk", AdapterKind.AGENT_FRAMEWORK, ("agent.invoke",)),
        AdapterDescriptor("semantic-kernel", AdapterKind.AGENT_FRAMEWORK, ("agent.invoke",)),
        AdapterDescriptor(
            "hermes",
            AdapterKind.AGENT_FRAMEWORK,
            ("agent.invoke", "intent.submit"),
            notes=("adapter requests remain proposal-only until canonical authorization",),
        ),
        AdapterDescriptor("mcp", AdapterKind.PROTOCOL, ("tools.list", "tools.call")),
        AdapterDescriptor(
            "frost-call",
            AdapterKind.PROTOCOL,
            ("intent.submit",),
            status=AdapterStatus.DISCOVERED,
            notes=(
                "frost-call ingress normalizes proposals into CanonicalAdapterGateway",
                "protocol membership never grants execution authority",
            ),
        ),
        AdapterDescriptor("a2a", AdapterKind.PROTOCOL, ("agent.message",)),
        AdapterDescriptor("nats", AdapterKind.MESSAGING, ("message.publish", "message.consume")),
        AdapterDescriptor("mqtt", AdapterKind.MESSAGING, ("message.publish", "message.consume")),
        AdapterDescriptor("zeromq", AdapterKind.MESSAGING, ("message.publish", "message.consume")),
        AdapterDescriptor("matrix", AdapterKind.MESSAGING, ("message.publish", "message.consume")),
        AdapterDescriptor(
            "websocket",
            AdapterKind.MESSAGING,
            ("message.publish", "message.consume"),
        ),
        AdapterDescriptor(
            "discord",
            AdapterKind.CONTROL_PLANE,
            ("message.publish", "message.consume", "intent.submit"),
            notes=("Discord transport does not grant execution authority",),
        ),
        AdapterDescriptor(
            "github-actions",
            AdapterKind.EXECUTION_PROVIDER,
            ("frost.call", "github.runtime.qualification_marker.put"),
            status=AdapterStatus.CONNECTED_VALIDATED,
            notes=(
                "github.runtime.qualification_marker.put is connected-validated through frost-effect/1.0",
                "no caller-supplied repository path, shell command, or network target is authorized",
                "generic Capability Factory PROMOTED is not asserted by this catalog status",
            ),
        ),
        AdapterDescriptor(
            "termux-local",
            AdapterKind.EXECUTION_PROVIDER,
            ("frost.call",),
            status=AdapterStatus.HOST_VALIDATED,
            local_only=True,
            notes=("physical Android validation remains separate",),
        ),
        AdapterDescriptor("vercel", AdapterKind.EXECUTION_PROVIDER, ("http.invoke", "mcp.call")),
        AdapterDescriptor(
            "base44",
            AdapterKind.CONTROL_PLANE,
            ("state.mirror", "job.rendezvous", "intent.submit"),
            notes=("control-plane mirror is not canonical state or authorization",),
        ),
        AdapterDescriptor(
            "aaard",
            AdapterKind.CONTROL_PLANE,
            ("intent.submit", "state.mirror"),
            notes=("legacy/domain requests normalize into canonical event state",),
        ),
        AdapterDescriptor(
            "fras",
            AdapterKind.CONTROL_PLANE,
            ("intent.submit", "research.claim.submit"),
            notes=("scientific task submission is not scientific validation",),
        ),
        AdapterDescriptor("v0", AdapterKind.SOFTWARE_CREATION, ("v0.chat.*", "v0.sync.prepare_pr")),
    )
    return FederationCatalog(descriptors)
