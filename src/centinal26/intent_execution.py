from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from .adapter_gateway import AdapterRequest, CanonicalAdapterGateway
from .control_plane import canonical_sha256
from .event_state import EventStore, rebuild_state
from .intent_operators import IntentMatch, IntentOperator, classify_intent

Json = dict[str, Any]
Capability = Callable[[Json], Json]
Verifier = Callable[[Json, Json], bool]


class IntentExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionPolicy:
    exact_execute_authorizes: bool = True
    require_registered_capability: bool = True
    require_verification: bool = True


@dataclass(frozen=True)
class VerticalExecutionResult:
    operator: str
    task_id: str
    capability: str
    authorized: bool
    executed: bool
    verified: bool
    completed: bool
    evidence_digest: str
    event_chain_valid: bool

    def as_dict(self) -> Json:
        return asdict(self)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, tuple[Capability, Verifier]] = {}

    def register(self, name: str, execute: Capability, verify: Verifier) -> None:
        if not name.strip():
            raise ValueError("capability name must not be empty")
        if name in self._capabilities:
            raise ValueError(f"capability already registered: {name}")
        self._capabilities[name] = (execute, verify)

    def resolve(self, name: str) -> tuple[Capability, Verifier]:
        try:
            return self._capabilities[name]
        except KeyError as exc:
            raise IntentExecutionError(f"unregistered capability: {name}") from exc


class IntentExecutionController:
    """Bounded ingress -> authorization -> execution -> evidence -> reconciliation."""

    def __init__(
        self,
        store: EventStore,
        registry: CapabilityRegistry,
        *,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self.store = store
        self.registry = registry
        self.policy = policy or ExecutionPolicy()
        self.gateway = CanonicalAdapterGateway(store)

    def ingest_and_execute(
        self,
        *,
        text: str,
        adapter_id: str,
        external_id: str,
        capability: str,
        payload: Json,
        constraints: Json | None = None,
        actor: str | None = None,
    ) -> VerticalExecutionResult:
        match = classify_intent(text)
        self._require_exact_execute(match)
        ingest = self.gateway.ingest(
            AdapterRequest(
                adapter_id=adapter_id,
                external_id=external_id,
                capability=capability,
                payload=payload,
                constraints=constraints or {},
                objective=f"{match.operator.value}: {capability}",
                actor=actor,
            )
        )
        task_id = ingest.task_id
        task = rebuild_state(self.store.events()).tasks[task_id]
        if task.get("status") != "DISCOVERED":
            raise IntentExecutionError(f"task is not authorization-ready: {task.get('status')}")

        execute, verify = self.registry.resolve(capability)
        self.store.append(
            "TASK_AUTHORIZED",
            {
                "task_id": task_id,
                "operator": match.operator.value,
                "authorization": "exact_user_execute_intent",
                "matched_phrase": match.matched_phrase,
                "confidence": match.confidence,
            },
            entity_id=task_id,
        )
        self.store.append(
            "TASK_STARTED", {"task_id": task_id, "capability": capability}, entity_id=task_id
        )
        try:
            output = execute(payload)
            if not isinstance(output, dict):
                raise TypeError("capability output must be a JSON object")
        except Exception as exc:
            self.store.append(
                "TASK_FAILED",
                {"task_id": task_id, "reason": f"execution_error:{type(exc).__name__}"},
                entity_id=task_id,
            )
            raise

        evidence = {
            "task_id": task_id,
            "capability": capability,
            "input_digest": canonical_sha256(payload),
            "output": output,
            "output_digest": canonical_sha256(output),
        }
        evidence_digest = canonical_sha256(evidence)
        self.store.append(
            "TASK_EXECUTED", {**evidence, "evidence_digest": evidence_digest}, entity_id=task_id
        )
        if not bool(verify(payload, output)):
            self.store.append(
                "VERIFICATION_FAILED",
                {"task_id": task_id, "evidence_digest": evidence_digest},
                entity_id=task_id,
            )
            raise IntentExecutionError("independent verification failed")
        self.store.append(
            "VERIFICATION_PASSED",
            {"task_id": task_id, "evidence_digest": evidence_digest},
            entity_id=task_id,
        )
        self.store.append(
            "TASK_COMPLETED",
            {"task_id": task_id, "evidence_digest": evidence_digest},
            entity_id=task_id,
        )
        completed = rebuild_state(self.store.events()).tasks[task_id].get("status") == "COMPLETE"
        return VerticalExecutionResult(
            operator=match.operator.value,
            task_id=task_id,
            capability=capability,
            authorized=True,
            executed=True,
            verified=True,
            completed=completed,
            evidence_digest=evidence_digest,
            event_chain_valid=self.store.verify_chain(),
        )

    def _require_exact_execute(self, match: IntentMatch | None) -> None:
        if match is None or match.operator is not IntentOperator.EXECUTE:
            raise IntentExecutionError("vertical execution currently requires EXECUTE intent")
        if not self.policy.exact_execute_authorizes or match.confidence != 1.0:
            raise IntentExecutionError("EXECUTE intent is not an exact authorization")
