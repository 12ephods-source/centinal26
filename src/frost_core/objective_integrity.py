from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Protocol


class ObjectiveSource(StrEnum):
    OWNER = "OWNER"
    OWNER_POLICY = "OWNER_POLICY"
    LOCAL_AGENT = "LOCAL_AGENT"
    REMOTE_AGENT = "REMOTE_AGENT"
    TOOL = "TOOL"
    IMPORTED_DOCUMENT = "IMPORTED_DOCUMENT"
    WEB = "WEB"
    UNKNOWN = "UNKNOWN"


class ObjectiveDecision(StrEnum):
    EXECUTE = "EXECUTE"
    PROPOSE_ONLY = "PROPOSE_ONLY"
    QUARANTINE = "QUARANTINE"
    DENY = "DENY"


EXECUTABLE_SOURCES = frozenset({
    ObjectiveSource.OWNER,
    ObjectiveSource.OWNER_POLICY,
})

DEFAULT_FORBIDDEN_CAPABILITIES = frozenset({
    "credential_export",
    "secret_read",
    "identity_change",
    "disable_logging",
    "delete_evidence",
    "modify_objective_registry",
    "unrestricted_network",
})


@dataclass(frozen=True)
class ObjectiveProposal:
    objective_id: str
    text: str
    source: ObjectiveSource
    source_ref: str
    root_objective: str
    parent_objective_id: str | None
    requested_capabilities: tuple[str, ...] = ()
    authorization_ref: str | None = None


@dataclass(frozen=True)
class ObjectiveEvaluation:
    objective_id: str
    decision: ObjectiveDecision
    reasons: tuple[str, ...]
    authorization_verified: bool


@dataclass(frozen=True)
class CapabilityToken:
    task_id: str
    objective_id: str
    root_objective: str
    allowed_actions: frozenset[str]
    network_scope: frozenset[str] = frozenset()
    allowed_secrets: frozenset[str] = frozenset()
    destructive_actions: bool = False


@dataclass(frozen=True)
class Action:
    name: str
    destination: str | None = None
    secret_id: str | None = None
    destructive: bool = False
    requires_network: bool = False


class AuthorizationVerifier(Protocol):
    """Trust boundary: verify owner authorization outside untrusted proposal data."""

    def verify(self, proposal: ObjectiveProposal) -> bool: ...


class ObjectStore(Protocol):
    """Subset of frost_core.object_store.CanonicalObjectStore used here."""

    def put(
        self,
        kind: str,
        payload: Any,
        *,
        source_type: str = "generated",
        source_ref: str = "",
        evidence_class: str = "UNCLASSIFIED",
        captured_at: float | None = None,
    ) -> str: ...

    def link(self, parent_id: str, relation: str, child_id: str) -> None: ...

    def point(self, alias: str, object_id: str, *, at: float | None = None) -> None: ...


class DenyAllAuthorizationVerifier:
    """Safe default. No authorization is inferred from user-controlled fields."""

    def verify(self, proposal: ObjectiveProposal) -> bool:
        return False


class ObjectiveIntegrityRegistry:
    """Fail-closed objective evaluation backed by the canonical object store.

    Any source may submit a proposal. Only OWNER / OWNER_POLICY sources may
    become executable, and their authorization must be verified outside the
    proposal payload. Unknown roots cannot be created by proposal. Objective
    authorization remains independent from capability promotion.
    """

    def __init__(
        self,
        store: ObjectStore,
        *,
        canonical_roots: Iterable[str],
        authorization_verifier: AuthorizationVerifier | None = None,
        forbidden_capabilities: Iterable[str] = DEFAULT_FORBIDDEN_CAPABILITIES,
    ) -> None:
        roots = frozenset(str(x).strip() for x in canonical_roots if str(x).strip())
        if not roots:
            raise ValueError("canonical_roots may not be empty")
        self.store = store
        self.canonical_roots = roots
        self.authorization_verifier = (
            authorization_verifier or DenyAllAuthorizationVerifier()
        )
        self.forbidden_capabilities = frozenset(forbidden_capabilities)

    def evaluate(self, proposal: ObjectiveProposal) -> ObjectiveEvaluation:
        reasons: list[str] = []

        if not proposal.objective_id.strip():
            return ObjectiveEvaluation(
                proposal.objective_id,
                ObjectiveDecision.DENY,
                ("missing_objective_id",),
                False,
            )
        if not proposal.text.strip():
            return ObjectiveEvaluation(
                proposal.objective_id,
                ObjectiveDecision.DENY,
                ("missing_objective_text",),
                False,
            )
        if not proposal.source_ref.strip():
            reasons.append("missing_source_ref")

        if proposal.source not in EXECUTABLE_SOURCES:
            reasons.append("non_owner_source")
            return ObjectiveEvaluation(
                proposal.objective_id,
                ObjectiveDecision.PROPOSE_ONLY,
                tuple(reasons),
                False,
            )

        if proposal.root_objective not in self.canonical_roots:
            reasons.append("unknown_root_objective")
            return ObjectiveEvaluation(
                proposal.objective_id,
                ObjectiveDecision.QUARANTINE,
                tuple(reasons),
                False,
            )

        forbidden = sorted(
            self.forbidden_capabilities.intersection(proposal.requested_capabilities)
        )
        if forbidden:
            reasons.extend(f"forbidden_capability:{x}" for x in forbidden)
            return ObjectiveEvaluation(
                proposal.objective_id,
                ObjectiveDecision.DENY,
                tuple(reasons),
                False,
            )

        verified = bool(self.authorization_verifier.verify(proposal))
        if not verified:
            reasons.append("authorization_not_verified")
            return ObjectiveEvaluation(
                proposal.objective_id,
                ObjectiveDecision.QUARANTINE,
                tuple(reasons),
                False,
            )

        return ObjectiveEvaluation(
            proposal.objective_id,
            ObjectiveDecision.EXECUTE,
            (),
            True,
        )

    def record(self, proposal: ObjectiveProposal) -> tuple[str, str, ObjectiveEvaluation]:
        """Persist proposal and decision. Promotion occurs only for EXECUTE."""

        evaluation = self.evaluate(proposal)
        proposal_id = self.store.put(
            "objective_proposal",
            {
                **asdict(proposal),
                "source": proposal.source.value,
            },
            source_type=proposal.source.value,
            source_ref=proposal.source_ref,
            evidence_class="UNTRUSTED_PROPOSAL"
            if proposal.source not in EXECUTABLE_SOURCES
            else "OWNER_ASSERTED_PROPOSAL",
        )
        decision_id = self.store.put(
            "objective_evaluation",
            {
                **asdict(evaluation),
                "decision": evaluation.decision.value,
            },
            source_type="objective_integrity",
            source_ref=proposal_id,
            evidence_class="AUTHORIZATION_DECISION",
        )
        self.store.link(proposal_id, "evaluated_as", decision_id)

        if evaluation.decision == ObjectiveDecision.EXECUTE:
            authorized_id = self.store.put(
                "authorized_objective",
                {
                    **asdict(proposal),
                    "source": proposal.source.value,
                    "evaluation_object_id": decision_id,
                },
                source_type="objective_integrity",
                source_ref=decision_id,
                evidence_class="OWNER_AUTHORIZED",
            )
            self.store.link(decision_id, "authorizes", authorized_id)
            self.store.point(f"objective/current/{proposal.objective_id}", authorized_id)

        return proposal_id, decision_id, evaluation


def child_capabilities_valid(parent: CapabilityToken, child: CapabilityToken) -> bool:
    """No capability amplification: C_child must be a subset of C_parent."""

    return (
        child.root_objective == parent.root_objective
        and child.objective_id == parent.objective_id
        and child.allowed_actions.issubset(parent.allowed_actions)
        and child.network_scope.issubset(parent.network_scope)
        and child.allowed_secrets.issubset(parent.allowed_secrets)
        and (not child.destructive_actions or parent.destructive_actions)
    )


def execution_gate(token: CapabilityToken, action: Action) -> bool:
    """Invocation-time authority check. Capability promotion alone is insufficient."""

    if action.name not in token.allowed_actions:
        return False
    if action.destructive and not token.destructive_actions:
        return False
    if action.requires_network and (
        not action.destination or action.destination not in token.network_scope
    ):
        return False
    return not (action.secret_id and action.secret_id not in token.allowed_secrets)
