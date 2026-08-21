from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from frost_core.object_store import CanonicalObjectStore
from frost_core.objective_integrity import Action, CapabilityToken, execution_gate

Json = dict[str, Any]


@dataclass(frozen=True)
class RuntimeGovernanceDecision:
    allowed: bool
    status: str
    reason: str
    objective_id: str | None = None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _string_set(value: Any) -> frozenset[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return None
    return frozenset(value)


def _capability_token(payload: Any) -> CapabilityToken | None:
    if not isinstance(payload, dict):
        return None
    task_id = _text(payload.get("task_id"))
    objective_id = _text(payload.get("objective_id"))
    root_objective = _text(payload.get("root_objective"))
    allowed_actions = _string_set(payload.get("allowed_actions"))
    network_scope = _string_set(payload.get("network_scope", []))
    allowed_secrets = _string_set(payload.get("allowed_secrets", []))
    destructive_actions = payload.get("destructive_actions", False)
    if (
        task_id is None
        or objective_id is None
        or root_objective is None
        or allowed_actions is None
        or network_scope is None
        or allowed_secrets is None
        or not isinstance(destructive_actions, bool)
    ):
        return None
    return CapabilityToken(
        task_id=task_id,
        objective_id=objective_id,
        root_objective=root_objective,
        allowed_actions=allowed_actions,
        network_scope=network_scope,
        allowed_secrets=allowed_secrets,
        destructive_actions=destructive_actions,
    )


def _has_provenance(
    store: CanonicalObjectStore,
    object_id: str,
    *,
    source_type: str,
    evidence_class: str,
) -> bool:
    return any(
        row.get("source_type") == source_type and row.get("evidence_class") == evidence_class
        for row in store.provenance(object_id)
    )


def verify_runtime_objective_context(
    store: CanonicalObjectStore,
    task: Json,
    *,
    action_name: str,
) -> RuntimeGovernanceDecision:
    """Fail closed before a consequential provider/process invocation.

    Authority is resolved from immutable canonical objects. Inline task claims never
    become authority. The capability token must be persisted by Guardian with the
    dedicated capability-authorization evidence class.
    """

    context = task.get("objective_context")
    if not isinstance(context, dict):
        return RuntimeGovernanceDecision(False, "OBJECTIVE_CONTEXT_REQUIRED", "missing_context")

    authorized_id = _text(context.get("authorized_objective_id"))
    evaluation_id = _text(context.get("objective_evaluation_id"))
    token_id = _text(context.get("capability_token_id"))
    if authorized_id is None or evaluation_id is None or token_id is None:
        return RuntimeGovernanceDecision(
            False,
            "OBJECTIVE_CONTEXT_INVALID",
            "missing_immutable_reference",
        )

    try:
        authorized = store.get(authorized_id)
        evaluation = store.get(evaluation_id)
        token_object = store.get(token_id)
    except KeyError:
        return RuntimeGovernanceDecision(
            False,
            "OBJECTIVE_REFERENCE_NOT_FOUND",
            "canonical_object_missing",
        )

    if authorized.kind != "authorized_objective":
        return RuntimeGovernanceDecision(False, "OBJECTIVE_CONTEXT_INVALID", "wrong_objective_kind")
    if evaluation.kind != "objective_evaluation":
        return RuntimeGovernanceDecision(False, "OBJECTIVE_CONTEXT_INVALID", "wrong_evaluation_kind")
    if token_object.kind != "capability_token":
        return RuntimeGovernanceDecision(False, "OBJECTIVE_CONTEXT_INVALID", "wrong_token_kind")
    if not isinstance(authorized.payload, dict) or not isinstance(evaluation.payload, dict):
        return RuntimeGovernanceDecision(False, "OBJECTIVE_CONTEXT_INVALID", "invalid_object_payload")

    objective_id = _text(authorized.payload.get("objective_id"))
    root_objective = _text(authorized.payload.get("root_objective"))
    if objective_id is None or root_objective is None:
        return RuntimeGovernanceDecision(False, "OBJECTIVE_CONTEXT_INVALID", "objective_identity_missing")
    if authorized.payload.get("evaluation_object_id") != evaluation_id:
        return RuntimeGovernanceDecision(
            False,
            "OBJECTIVE_CONTEXT_INVALID",
            "objective_evaluation_binding_mismatch",
            objective_id,
        )
    if (
        evaluation.payload.get("objective_id") != objective_id
        or evaluation.payload.get("decision") != "EXECUTE"
        or evaluation.payload.get("authorization_verified") is not True
    ):
        return RuntimeGovernanceDecision(
            False,
            "OBJECTIVE_NOT_AUTHORIZED",
            "evaluation_not_executable",
            objective_id,
        )
    if not _has_provenance(
        store,
        authorized_id,
        source_type="objective_integrity",
        evidence_class="OWNER_AUTHORIZED",
    ):
        return RuntimeGovernanceDecision(
            False,
            "OBJECTIVE_NOT_AUTHORIZED",
            "objective_provenance_invalid",
            objective_id,
        )

    try:
        current = store.resolve(f"objective/current/{objective_id}")
    except KeyError:
        return RuntimeGovernanceDecision(
            False,
            "OBJECTIVE_NOT_CURRENT",
            "current_objective_alias_missing",
            objective_id,
        )
    if current.object_id != authorized_id:
        return RuntimeGovernanceDecision(
            False,
            "OBJECTIVE_NOT_CURRENT",
            "authorized_objective_superseded",
            objective_id,
        )

    if not _has_provenance(
        store,
        token_id,
        source_type="guardian",
        evidence_class="CAPABILITY_AUTHORIZATION",
    ):
        return RuntimeGovernanceDecision(
            False,
            "CAPABILITY_TOKEN_INVALID",
            "guardian_provenance_missing",
            objective_id,
        )

    token = _capability_token(token_object.payload)
    if token is None:
        return RuntimeGovernanceDecision(
            False,
            "CAPABILITY_TOKEN_INVALID",
            "token_payload_invalid",
            objective_id,
        )
    if token.objective_id != objective_id or token.root_objective != root_objective:
        return RuntimeGovernanceDecision(
            False,
            "CAPABILITY_TOKEN_INVALID",
            "token_objective_binding_mismatch",
            objective_id,
        )
    if _text(task.get("task_id")) != token.task_id:
        return RuntimeGovernanceDecision(
            False,
            "CAPABILITY_TOKEN_INVALID",
            "token_task_binding_mismatch",
            objective_id,
        )

    action = Action(
        name=action_name,
        destination=_text(task.get("network_destination")),
        secret_id=_text(task.get("secret_id")),
        destructive=task.get("destructive") is True,
        requires_network=task.get("requires_network") is True,
    )
    if not execution_gate(token, action):
        return RuntimeGovernanceDecision(
            False,
            "CAPABILITY_SCOPE_DENIED",
            "invocation_scope_exceeds_token",
            objective_id,
        )

    return RuntimeGovernanceDecision(True, "OBJECTIVE_AUTHORIZED", "runtime_gate_passed", objective_id)
