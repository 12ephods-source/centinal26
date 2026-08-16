from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from centinal26.control_plane import (
    EvidenceRecord,
    MutationContract,
    OperationLedger,
    ProofResult,
    SagaStep,
    canonical_sha256,
    hourly_epoch,
    prove_mutation,
)
from centinal26.event_state import EventStore
from centinal26.mirror_evidence import canonical_mirror_projection, mirror_record_hash

CANONICAL_REPOSITORY = "12ephods-source/centinal26"
CANONICAL_BASE44_APP_ID = "6a484dc22829dd2fd4a7bcd1"
PROVIDER_AUTHORITY_SCHEMA = "centinal26-provider-mutation-authority-v1"
PROVIDER_BRIDGE_SCHEMA = "centinal26-github-base44-provider-bridge-v1"
EVIDENCE_TTL_SECONDS = 60

_LOGICAL_ID_FIELD = {
    "AutomationRoleResult": "result_id",
    "AutomationVerificationVerdict": "verdict_id",
}
_REQUIRED_FIELDS = {
    "AutomationRoleResult": {
        "result_id",
        "contract_id",
        "role",
        "status",
        "payload_json",
        "result_hash",
        "created_at_client",
    },
    "AutomationVerificationVerdict": {
        "verdict_id",
        "result_id",
        "contract_id",
        "verdict",
        "verifier",
        "details_json",
        "verdict_hash",
        "created_at_client",
    },
}
_OPTIONAL_FIELDS = {"evidence_hash"}
_ADMIN_RLS = {"user_condition": {"role": "admin"}}


class ProviderOutcomeAmbiguous(RuntimeError):
    """A provider write may have happened, but its final state cannot be proven."""


class ProviderBridgeState(StrEnum):
    COMMITTED = "COMMITTED"
    COMPENSATED = "COMPENSATED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass(frozen=True)
class ProviderSagaResult:
    state: ProviderBridgeState
    completed: tuple[str, ...]
    compensated: tuple[str, ...]
    error: str | None


class ProviderSagaRunner:
    """Saga runner that never compensates across an ambiguous provider outcome."""

    def execute(self, steps: Sequence[SagaStep]) -> ProviderSagaResult:
        completed: list[tuple[SagaStep, Any]] = []
        try:
            for step in steps:
                result = step.forward()
                if not step.postcondition(result):
                    raise RuntimeError(f"postcondition_failed:{step.name}")
                completed.append((step, result))
        except ProviderOutcomeAmbiguous as error:
            return ProviderSagaResult(
                state=ProviderBridgeState.RECOVERY_REQUIRED,
                completed=tuple(step.name for step, _ in completed),
                compensated=(),
                error=f"{type(error).__name__}:{error}",
            )
        except Exception as error:  # noqa: BLE001 - transaction boundary emits evidence
            compensated: list[str] = []
            failures: list[str] = []
            for step, result in reversed(completed):
                try:
                    compensation = step.compensate(result)
                    if step.compensation_postcondition(compensation):
                        compensated.append(step.name)
                    else:
                        failures.append(f"compensation_postcondition_failed:{step.name}")
                except Exception as compensation_error:  # noqa: BLE001 - evidence boundary
                    failures.append(
                        f"compensation_failed:{step.name}:{type(compensation_error).__name__}"
                    )
            state = (
                ProviderBridgeState.COMPENSATION_FAILED
                if failures
                else ProviderBridgeState.COMPENSATED
            )
            return ProviderSagaResult(
                state=state,
                completed=tuple(step.name for step, _ in completed),
                compensated=tuple(compensated),
                error=";".join([f"{type(error).__name__}:{error}", *failures]),
            )
        return ProviderSagaResult(
            state=ProviderBridgeState.COMMITTED,
            completed=tuple(step.name for step, _ in completed),
            compensated=(),
            error=None,
        )


@dataclass(frozen=True)
class GitHubPullRequestSnapshot:
    repository: str
    number: int
    node_id: str
    head_sha: str
    base_sha: str
    state: str
    draft: bool
    observed_at: str


class GitHubPullRequestTransport(Protocol):
    def actor_identity(self) -> str: ...

    def observe_pull_request(
        self, repository: str, number: int
    ) -> GitHubPullRequestSnapshot: ...

    def set_ready(
        self,
        repository: str,
        number: int,
        *,
        ready: bool,
        expected_head_sha: str,
    ) -> GitHubPullRequestSnapshot: ...


class Base44MirrorTransport(Protocol):
    def actor_identity(self) -> str: ...

    def observe_schema(self, app_id: str, entity_name: str) -> Mapping[str, Any]: ...

    def observe_record(
        self,
        app_id: str,
        entity_name: str,
        logical_id_field: str,
        logical_id: str,
    ) -> Mapping[str, Any] | None: ...

    def create_record(
        self,
        app_id: str,
        entity_name: str,
        record: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...

    def delete_record_if_projection_matches(
        self,
        app_id: str,
        entity_name: str,
        logical_id_field: str,
        logical_id: str,
        expected_projection_sha256: str,
    ) -> bool: ...


class GitHubGraphQLTransport:
    """Exact-head GitHub readiness transport; merge/rebase/close are intentionally absent."""

    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.github.com",
        graphql_url: str = "https://api.github.com/graphql",
        timeout_seconds: int = 20,
    ) -> None:
        if not token.strip():
            raise ValueError("GitHub token must not be empty")
        self.token = token.strip()
        self.api_url = api_url.rstrip("/")
        self.graphql_url = graphql_url
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        body = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "centinal26-provider-bridge/1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if payload is not None:
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"github_http_error:{error.code}:{detail[:500]}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"github_transport_error:{error.reason}") from error

    def actor_identity(self) -> str:
        value = self._request(f"{self.api_url}/user")
        login = value.get("login") if isinstance(value, dict) else None
        if not isinstance(login, str) or not login:
            raise RuntimeError("github_actor_identity_missing")
        return f"github:{login}"

    def observe_pull_request(
        self, repository: str, number: int
    ) -> GitHubPullRequestSnapshot:
        if repository != CANONICAL_REPOSITORY:
            raise ValueError("noncanonical GitHub repository")
        value = self._request(f"{self.api_url}/repos/{repository}/pulls/{number}")
        if not isinstance(value, dict):
            raise TypeError("github_pr_observation_invalid")
        head = value.get("head")
        base = value.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise TypeError("github_pr_identity_missing")
        node_id = value.get("node_id")
        head_sha = head.get("sha")
        base_sha = base.get("sha")
        state = value.get("state")
        draft = value.get("draft")
        strings = (node_id, head_sha, base_sha, state)
        if not all(isinstance(item, str) and item for item in strings):
            raise RuntimeError("github_pr_identity_missing")
        if not isinstance(draft, bool):
            raise TypeError("github_pr_draft_state_missing")
        return GitHubPullRequestSnapshot(
            repository=repository,
            number=number,
            node_id=node_id,
            head_sha=head_sha,
            base_sha=base_sha,
            state=state,
            draft=draft,
            observed_at=datetime.now(UTC).isoformat(),
        )

    def set_ready(
        self,
        repository: str,
        number: int,
        *,
        ready: bool,
        expected_head_sha: str,
    ) -> GitHubPullRequestSnapshot:
        before = self.observe_pull_request(repository, number)
        if before.head_sha != expected_head_sha:
            raise RuntimeError("github_head_changed_before_write")
        if before.state != "open":
            raise RuntimeError("github_pr_not_open")
        desired_draft = not ready
        if before.draft == desired_draft:
            return before
        field = "markPullRequestReadyForReview" if ready else "convertPullRequestToDraft"
        mutation = (
            "mutation($id: ID!) { "
            f"{field}(input: {{pullRequestId: $id}}) {{ pullRequest {{ id isDraft }} }} "
            "}"
        )
        write_error: Exception | None = None
        try:
            response = self._request(
                self.graphql_url,
                method="POST",
                payload={"query": mutation, "variables": {"id": before.node_id}},
            )
            if not isinstance(response, dict) or response.get("errors"):
                raise RuntimeError(f"github_graphql_error:{response!r}")
        except Exception as error:  # noqa: BLE001 - fresh read determines final state
            write_error = error
        try:
            after = self.observe_pull_request(repository, number)
        except Exception as error:
            raise ProviderOutcomeAmbiguous("github_ready_outcome_unobservable") from error
        if after.head_sha != expected_head_sha:
            raise ProviderOutcomeAmbiguous("github_head_changed_during_write")
        if after.state == "open" and after.draft == desired_draft:
            return after
        if write_error is not None and after.draft == before.draft:
            raise RuntimeError("github_ready_write_failed_confirmed_unchanged") from write_error
        raise ProviderOutcomeAmbiguous("github_ready_outcome_conflicting")


def _logical_id_field(entity_name: str) -> str:
    try:
        return _LOGICAL_ID_FIELD[entity_name]
    except KeyError:
        raise ValueError(f"unsupported Base44 mirror entity: {entity_name}") from None


def validate_base44_mirror_schema(entity_name: str, schema: Mapping[str, Any]) -> str:
    if entity_name not in _REQUIRED_FIELDS:
        raise ValueError(f"unsupported Base44 mirror entity: {entity_name}")
    properties = schema.get("properties")
    required = schema.get("required")
    rls = schema.get("rls")
    if schema.get("name") != entity_name or not isinstance(properties, Mapping):
        raise ValueError("base44_schema_identity_mismatch")
    if set(properties) != _REQUIRED_FIELDS[entity_name] | _OPTIONAL_FIELDS:
        raise ValueError("base44_schema_field_set_mismatch")
    if not isinstance(required, list) or set(required) != _REQUIRED_FIELDS[entity_name]:
        raise ValueError("base44_schema_required_set_mismatch")
    if not isinstance(rls, Mapping):
        raise TypeError("base44_schema_rls_missing")
    for operation in ("create", "read", "update", "delete"):
        if rls.get(operation) != _ADMIN_RLS:
            raise ValueError(f"base44_schema_rls_mismatch:{operation}")
    if entity_name == "AutomationRoleResult":
        allowed = {"GOVERNOR", "BUILDER", "JUDGE", "SRE", "EVOLUTION"}
        role = properties.get("role")
        if not isinstance(role, Mapping) or set(role.get("enum", [])) != allowed:
            raise ValueError("base44_schema_role_enum_mismatch")
    else:
        allowed = {"VERIFIED", "VERIFICATION_FAILED", "INCONCLUSIVE", "BLOCKED_EXTERNAL"}
        verdict = properties.get("verdict")
        if not isinstance(verdict, Mapping) or set(verdict.get("enum", [])) != allowed:
            raise ValueError("base44_schema_verdict_enum_mismatch")
    return canonical_sha256(schema)


@dataclass(frozen=True)
class Base44MirrorSnapshot:
    app_id: str
    entity_name: str
    logical_id: str
    schema_sha256: str
    projection_sha256: str | None
    observed_at: str


class Base44MirrorAdapter:
    """Canonical-app, schema-pinned, compare-before-delete Base44 mirror adapter."""

    def __init__(self, transport: Base44MirrorTransport) -> None:
        self.transport = transport

    def actor_identity(self) -> str:
        identity = self.transport.actor_identity().strip()
        if not identity.startswith("base44:"):
            raise RuntimeError("base44_actor_identity_invalid")
        return identity

    def observe(self, entity_name: str, logical_id: str) -> Base44MirrorSnapshot:
        schema = self.transport.observe_schema(CANONICAL_BASE44_APP_ID, entity_name)
        schema_sha = validate_base44_mirror_schema(entity_name, schema)
        logical_field = _logical_id_field(entity_name)
        record = self.transport.observe_record(
            CANONICAL_BASE44_APP_ID, entity_name, logical_field, logical_id
        )
        projection_sha = None
        if record is not None:
            projection_sha = mirror_record_hash(
                record, mirror_kind=entity_name, mirror_id=logical_id
            )
        return Base44MirrorSnapshot(
            app_id=CANONICAL_BASE44_APP_ID,
            entity_name=entity_name,
            logical_id=logical_id,
            schema_sha256=schema_sha,
            projection_sha256=projection_sha,
            observed_at=datetime.now(UTC).isoformat(),
        )

    def create_exact(
        self, entity_name: str, logical_id: str, record: Mapping[str, Any]
    ) -> Base44MirrorSnapshot:
        expected = mirror_record_hash(
            record, mirror_kind=entity_name, mirror_id=logical_id
        )
        if self.observe(entity_name, logical_id).projection_sha256 is not None:
            raise RuntimeError("base44_mirror_already_exists")
        write_error: Exception | None = None
        try:
            self.transport.create_record(CANONICAL_BASE44_APP_ID, entity_name, record)
        except Exception as error:  # noqa: BLE001 - resolved by read-after-write
            write_error = error
        try:
            after = self.observe(entity_name, logical_id)
        except Exception as error:
            raise ProviderOutcomeAmbiguous("base44_create_outcome_unobservable") from error
        if after.projection_sha256 == expected:
            return after
        if write_error is not None and after.projection_sha256 is None:
            raise RuntimeError("base44_create_failed_confirmed_absent") from write_error
        raise ProviderOutcomeAmbiguous("base44_create_outcome_conflicting")

    def delete_exact(
        self, entity_name: str, logical_id: str, expected_projection_sha256: str
    ) -> bool:
        before = self.observe(entity_name, logical_id)
        if before.projection_sha256 != expected_projection_sha256:
            return False
        deleted = self.transport.delete_record_if_projection_matches(
            CANONICAL_BASE44_APP_ID,
            entity_name,
            _logical_id_field(entity_name),
            logical_id,
            expected_projection_sha256,
        )
        if not deleted:
            return False
        return self.observe(entity_name, logical_id).projection_sha256 is None


@dataclass(frozen=True)
class ProviderAuthorityReference:
    event_id: str
    event_hash: str

    @property
    def identity(self) -> str:
        return f"canonical-event:{self.event_id}:{self.event_hash}"


@dataclass(frozen=True)
class ProviderMutationSpec:
    operation_id: str
    idempotency_key: str
    repository: str
    pull_request_number: int
    expected_head_sha: str
    expected_base_sha: str
    base44_entity: str
    base44_logical_id: str
    base44_record: Mapping[str, Any]
    expected_github_actor: str
    expected_base44_actor: str
    authority: ProviderAuthorityReference
    authority_scope: str = "github.pr.ready+base44.mirror.create"

    def __post_init__(self) -> None:
        if self.repository != CANONICAL_REPOSITORY:
            raise ValueError("provider bridge is hard-bound to the canonical repository")
        if self.pull_request_number < 1:
            raise ValueError("pull_request_number must be positive")
        canonical_mirror_projection(
            mirror_kind=self.base44_entity,
            mirror_id=self.base44_logical_id,
            mirror_record=self.base44_record,
        )


def provider_authority_grant(
    spec: ProviderMutationSpec,
    *,
    expires_at: str,
    actions: Sequence[str] = ("base44.mirror.create", "github.pull_request.ready"),
) -> dict[str, Any]:
    return {
        "schema": PROVIDER_AUTHORITY_SCHEMA,
        "outcome": "ALLOW",
        "operation_id": spec.operation_id,
        "repository": spec.repository,
        "pull_request_number": spec.pull_request_number,
        "expected_head_sha": spec.expected_head_sha,
        "expected_base_sha": spec.expected_base_sha,
        "base44_app_id": CANONICAL_BASE44_APP_ID,
        "base44_entity": spec.base44_entity,
        "base44_logical_id": spec.base44_logical_id,
        "expected_github_actor": spec.expected_github_actor,
        "expected_base44_actor": spec.expected_base44_actor,
        "authority_scope": spec.authority_scope,
        "actions": sorted(set(actions)),
        "expires_at": expires_at,
    }


def verify_provider_authority(
    store: EventStore,
    spec: ProviderMutationSpec,
    *,
    action: str,
    now: datetime,
) -> EvidenceRecord:
    if not store.verify_chain():
        raise PermissionError("canonical_event_chain_invalid")
    event = next(
        (item for item in store.events() if item.event_id == spec.authority.event_id), None
    )
    if event is None:
        raise PermissionError("provider_authority_event_missing")
    if event.event_hash != spec.authority.event_hash:
        raise PermissionError("provider_authority_event_hash_mismatch")
    if event.type != "DECISION_RECORDED":
        raise PermissionError("provider_authority_event_type_invalid")
    grant = event.payload.get("provider_mutation_grant")
    if not isinstance(grant, dict):
        raise PermissionError("provider_authority_grant_missing")
    if grant.get("schema") != PROVIDER_AUTHORITY_SCHEMA or grant.get("outcome") != "ALLOW":
        raise PermissionError("provider_authority_grant_not_allow")
    actions = grant.get("actions")
    if not isinstance(actions, list) or action not in actions:
        raise PermissionError(f"provider_authority_action_missing:{action}")
    expected = provider_authority_grant(
        spec,
        expires_at=str(grant.get("expires_at", "")),
        actions=actions,
    )
    if grant != expected:
        raise PermissionError("provider_authority_grant_identity_mismatch")
    expires = datetime.fromisoformat(str(grant["expires_at"]))
    if expires.tzinfo is None or now.astimezone(UTC) > expires.astimezone(UTC):
        raise PermissionError("provider_authority_grant_expired")
    return EvidenceRecord(
        evidence_id=f"authority:{event.event_id}:{action}",
        kind="authority",
        subject=spec.authority.identity,
        source="canonical-event-store",
        acquired_at=now.astimezone(UTC).isoformat(),
        ttl_seconds=EVIDENCE_TTL_SECONDS,
        digest=event.event_hash,
        provenance="internal",
        run_id=spec.operation_id,
        epoch=hourly_epoch(now),
    )


def _external_evidence(
    *,
    evidence_id: str,
    kind: str,
    subject: str,
    source: str,
    value: Any,
    acquired_at: datetime,
    run_id: str,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        kind=kind,
        subject=subject,
        source=source,
        acquired_at=acquired_at.astimezone(UTC).isoformat(),
        ttl_seconds=EVIDENCE_TTL_SECONDS,
        digest=canonical_sha256(value),
        provenance="external",
        run_id=run_id,
        epoch=hourly_epoch(acquired_at),
    )


@dataclass(frozen=True)
class ProviderBridgeResult:
    schema: str
    operation_id: str
    state: ProviderBridgeState
    saga: ProviderSagaResult
    base44_proof: ProofResult | None
    github_proof: ProofResult | None
    result_digest: str
    replay_blocked: bool


class GitHubBase44ReadyBridge:
    """Stage a non-authoritative Base44 mirror, then make one exact PR ready."""

    def __init__(
        self,
        *,
        event_store: EventStore,
        ledger: OperationLedger,
        github: GitHubPullRequestTransport,
        base44: Base44MirrorTransport,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.event_store = event_store
        self.ledger = ledger
        self.github = github
        self.base44 = Base44MirrorAdapter(base44)
        self.clock = clock or (lambda: datetime.now(UTC))

    def _prove_base44(self, spec: ProviderMutationSpec) -> ProofResult:
        observed_at = self.clock()
        authority = verify_provider_authority(
            self.event_store, spec, action="base44.mirror.create", now=observed_at
        )
        actor = self.base44.actor_identity()
        snapshot = self.base44.observe(spec.base44_entity, spec.base44_logical_id)
        target = f"base44:{CANONICAL_BASE44_APP_ID}/{spec.base44_entity}/{spec.base44_logical_id}"
        contract = MutationContract(
            operation_id=f"{spec.operation_id}:base44-stage",
            authority=spec.authority.identity,
            actor_identity=spec.expected_base44_actor,
            target_identity=target,
            preconditions=("base44_schema_pinned", "base44_mirror_absent"),
            blast_radius=1,
            rollback_plan="delete only the exact unchanged staged projection",
            postconditions=("base44_mirror_projection_exact",),
            idempotency_key=spec.idempotency_key,
            evidence_required=("authority", "identity", "target", "preconditions"),
        )
        preconditions = {
            "base44_schema_pinned": bool(snapshot.schema_sha256),
            "base44_mirror_absent": snapshot.projection_sha256 is None,
        }
        evidence = [
            authority,
            _external_evidence(
                evidence_id=f"identity:{spec.operation_id}:base44",
                kind="identity",
                subject=actor,
                source="base44",
                value={"actor": actor},
                acquired_at=observed_at,
                run_id=spec.operation_id,
            ),
            _external_evidence(
                evidence_id=f"target:{spec.operation_id}:base44",
                kind="target",
                subject=target,
                source="base44",
                value=asdict(snapshot),
                acquired_at=observed_at,
                run_id=spec.operation_id,
            ),
            _external_evidence(
                evidence_id=f"preconditions:{spec.operation_id}:base44",
                kind="preconditions",
                subject=target,
                source="base44",
                value=preconditions,
                acquired_at=observed_at,
                run_id=spec.operation_id,
            ),
        ]
        return prove_mutation(
            contract, evidence, preconditions, now=self.clock(), ledger=self.ledger
        )

    def _prove_github(self, spec: ProviderMutationSpec) -> ProofResult:
        observed_at = self.clock()
        authority = verify_provider_authority(
            self.event_store, spec, action="github.pull_request.ready", now=observed_at
        )
        actor = self.github.actor_identity().strip()
        pr = self.github.observe_pull_request(spec.repository, spec.pull_request_number)
        mirror = self.base44.observe(spec.base44_entity, spec.base44_logical_id)
        expected_mirror = mirror_record_hash(
            spec.base44_record,
            mirror_kind=spec.base44_entity,
            mirror_id=spec.base44_logical_id,
        )
        target = f"github:{spec.repository}#pr-{spec.pull_request_number}@{spec.expected_head_sha}"
        contract = MutationContract(
            operation_id=f"{spec.operation_id}:github-ready",
            authority=spec.authority.identity,
            actor_identity=spec.expected_github_actor,
            target_identity=target,
            preconditions=(
                "github_pr_open",
                "github_pr_draft",
                "github_head_exact",
                "github_base_exact",
                "base44_stage_exact",
            ),
            blast_radius=2,
            rollback_plan="preserve staged mirror if GitHub outcome is ambiguous",
            postconditions=("github_pr_ready_exact_head",),
            idempotency_key=spec.idempotency_key,
            evidence_required=("authority", "identity", "target", "preconditions"),
        )
        preconditions = {
            "github_pr_open": pr.state == "open",
            "github_pr_draft": pr.draft is True,
            "github_head_exact": pr.head_sha == spec.expected_head_sha,
            "github_base_exact": pr.base_sha == spec.expected_base_sha,
            "base44_stage_exact": mirror.projection_sha256 == expected_mirror,
        }
        evidence = [
            authority,
            _external_evidence(
                evidence_id=f"identity:{spec.operation_id}:github",
                kind="identity",
                subject=actor,
                source="github",
                value={"actor": actor},
                acquired_at=observed_at,
                run_id=spec.operation_id,
            ),
            _external_evidence(
                evidence_id=f"target:{spec.operation_id}:github",
                kind="target",
                subject=target,
                source="github+base44",
                value={"github": asdict(pr), "base44": asdict(mirror)},
                acquired_at=observed_at,
                run_id=spec.operation_id,
            ),
            _external_evidence(
                evidence_id=f"preconditions:{spec.operation_id}:github",
                kind="preconditions",
                subject=target,
                source="github+base44",
                value=preconditions,
                acquired_at=observed_at,
                run_id=spec.operation_id,
            ),
        ]
        return prove_mutation(
            contract, evidence, preconditions, now=self.clock(), ledger=self.ledger
        )

    @staticmethod
    def _require(proof: ProofResult, label: str) -> None:
        if not proof.passed:
            raise PermissionError(f"{label}_proof_failed:{','.join(proof.reasons)}")

    def execute(self, spec: ProviderMutationSpec) -> ProviderBridgeResult:
        if self.ledger.contains(spec.idempotency_key):
            raise PermissionError("provider_bridge_replay_blocked")
        expected_mirror = mirror_record_hash(
            spec.base44_record,
            mirror_kind=spec.base44_entity,
            mirror_id=spec.base44_logical_id,
        )
        base44_proof: ProofResult | None = None
        github_proof: ProofResult | None = None

        def stage() -> Base44MirrorSnapshot:
            nonlocal base44_proof
            base44_proof = self._prove_base44(spec)
            self._require(base44_proof, "base44")
            return self.base44.create_exact(
                spec.base44_entity, spec.base44_logical_id, spec.base44_record
            )

        def ready() -> GitHubPullRequestSnapshot:
            nonlocal github_proof
            github_proof = self._prove_github(spec)
            self._require(github_proof, "github")
            return self.github.set_ready(
                spec.repository,
                spec.pull_request_number,
                ready=True,
                expected_head_sha=spec.expected_head_sha,
            )

        saga = ProviderSagaRunner().execute(
            [
                SagaStep(
                    name="base44-stage",
                    forward=stage,
                    postcondition=lambda value: value.projection_sha256 == expected_mirror,
                    compensate=lambda _: self.base44.delete_exact(
                        spec.base44_entity, spec.base44_logical_id, expected_mirror
                    ),
                    compensation_postcondition=lambda value: value is True,
                ),
                SagaStep(
                    name="github-ready",
                    forward=ready,
                    postcondition=lambda value: (
                        value.repository == spec.repository
                        and value.number == spec.pull_request_number
                        and value.head_sha == spec.expected_head_sha
                        and value.base_sha == spec.expected_base_sha
                        and value.state == "open"
                        and value.draft is False
                    ),
                    compensate=lambda _: True,
                    compensation_postcondition=lambda value: value is True,
                ),
            ]
        )
        body = {
            "schema": PROVIDER_BRIDGE_SCHEMA,
            "operation_id": spec.operation_id,
            "state": saga.state.value,
            "saga": asdict(saga),
            "base44_proof": asdict(base44_proof) if base44_proof else None,
            "github_proof": asdict(github_proof) if github_proof else None,
            "expected_mirror_sha256": expected_mirror,
        }
        result_digest = canonical_sha256(body)
        replay_blocked = saga.state in {
            ProviderBridgeState.COMMITTED,
            ProviderBridgeState.COMPENSATION_FAILED,
            ProviderBridgeState.RECOVERY_REQUIRED,
        }
        if replay_blocked:
            self.ledger.record(spec.idempotency_key, result_digest)
        return ProviderBridgeResult(
            schema=PROVIDER_BRIDGE_SCHEMA,
            operation_id=spec.operation_id,
            state=saga.state,
            saga=saga,
            base44_proof=base44_proof,
            github_proof=github_proof,
            result_digest=result_digest,
            replay_blocked=replay_blocked,
        )


def default_provider_ledger(state_root: Path) -> OperationLedger:
    return OperationLedger(state_root / "control-plane" / "provider-operations.json")
