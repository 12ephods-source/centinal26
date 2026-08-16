from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from centinal26.control_plane import (
    CompensationUnsafeError,
    EvidenceRecord,
    MutationContract,
    OperationLedger,
    ProofResult,
    SagaResult,
    SagaRunner,
    SagaState,
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
PROVIDER_SAGA_SCHEMA = "centinal26-github-base44-saga-v1"
DEFAULT_EVIDENCE_TTL_SECONDS = 60

_MIRROR_LOGICAL_ID_FIELD = {
    "AutomationRoleResult": "result_id",
    "AutomationVerificationVerdict": "verdict_id",
}
_MIRROR_REQUIRED_FIELDS = {
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
_MIRROR_OPTIONAL_FIELDS = {"evidence_hash"}
_ADMIN_RLS = {"user_condition": {"role": "admin"}}


class ProviderSchemaError(ValueError):
    """The live provider schema does not match the pinned consequential-write contract."""


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

    def digest(self) -> str:
        return canonical_sha256(asdict(self))


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
    """Minimal GitHub REST/GraphQL transport with exact-head postcondition checks.

    This transport performs only pull-request draft/readiness transitions. It does not
    merge, close, rebase, delete branches, or alter release state. A write whose final
    provider state cannot be observed is treated as ambiguous and must not trigger an
    automatic cross-provider rollback.
    """

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
            "User-Agent": "centinal26-provider-saga/1",
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
            text = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"github_http_error:{error.code}:{text[:500]}") from error
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
            raise RuntimeError("github_pull_request_observation_invalid")
        head = value.get("head")
        base = value.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise RuntimeError("github_pull_request_identity_missing")
        node_id = value.get("node_id")
        head_sha = head.get("sha")
        base_sha = base.get("sha")
        state = value.get("state")
        draft = value.get("draft")
        if not all(isinstance(item, str) and item for item in (node_id, head_sha, base_sha, state)):
            raise RuntimeError("github_pull_request_identity_missing")
        if not isinstance(draft, bool):
            raise RuntimeError("github_pull_request_draft_state_missing")
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
            raise RuntimeError("github_pull_request_not_open")
        desired_draft = not ready
        if before.draft == desired_draft:
            return before

        if ready:
            mutation = """
                mutation($id: ID!) {
                  markPullRequestReadyForReview(input: {pullRequestId: $id}) {
                    pullRequest { id isDraft }
                  }
                }
            """
        else:
            mutation = """
                mutation($id: ID!) {
                  convertPullRequestToDraft(input: {pullRequestId: $id}) {
                    pullRequest { id isDraft }
                  }
                }
            """

        write_error: Exception | None = None
        try:
            response = self._request(
                self.graphql_url,
                method="POST",
                payload={"query": mutation, "variables": {"id": before.node_id}},
            )
            if not isinstance(response, dict) or response.get("errors"):
                raise RuntimeError(f"github_graphql_error:{response!r}")
        except Exception as error:  # noqa: BLE001 - state is resolved by a fresh read below
            write_error = error

        try:
            after = self.observe_pull_request(repository, number)
        except Exception as observe_error:  # noqa: BLE001 - ambiguous provider outcome
            raise CompensationUnsafeError(
                f"github_write_outcome_ambiguous:{type(observe_error).__name__}"
            ) from observe_error

        if after.head_sha != expected_head_sha:
            raise CompensationUnsafeError("github_head_changed_during_write")
        if after.draft == desired_draft and after.state == "open":
            return after
        if write_error is not None and after.draft == before.draft:
            raise RuntimeError("github_write_failed_confirmed_unchanged") from write_error
        raise CompensationUnsafeError("github_write_outcome_ambiguous")


def _logical_id_field(entity_name: str) -> str:
    try:
        return _MIRROR_LOGICAL_ID_FIELD[entity_name]
    except KeyError:
        raise ProviderSchemaError(f"unsupported Base44 mirror entity: {entity_name}") from None


def validate_base44_mirror_schema(entity_name: str, schema: Mapping[str, Any]) -> str:
    """Validate the live Base44 entity contract including its admin-only RLS."""

    if entity_name not in _MIRROR_REQUIRED_FIELDS:
        raise ProviderSchemaError(f"unsupported Base44 mirror entity: {entity_name}")
    name = schema.get("name")
    properties = schema.get("properties")
    required = schema.get("required")
    rls = schema.get("rls")
    if name != entity_name or not isinstance(properties, Mapping):
        raise ProviderSchemaError("base44_schema_identity_mismatch")
    allowed_fields = _MIRROR_REQUIRED_FIELDS[entity_name] | _MIRROR_OPTIONAL_FIELDS
    if set(properties) != allowed_fields:
        raise ProviderSchemaError("base44_schema_field_set_mismatch")
    if not isinstance(required, list) or set(required) != _MIRROR_REQUIRED_FIELDS[entity_name]:
        raise ProviderSchemaError("base44_schema_required_set_mismatch")
    if not isinstance(rls, Mapping):
        raise ProviderSchemaError("base44_schema_rls_missing")
    for operation in ("create", "read", "update", "delete"):
        if rls.get(operation) != _ADMIN_RLS:
            raise ProviderSchemaError(f"base44_schema_rls_mismatch:{operation}")

    if entity_name == "AutomationRoleResult":
        role = properties.get("role")
        expected_roles = {"GOVERNOR", "BUILDER", "JUDGE", "SRE", "EVOLUTION"}
        if not isinstance(role, Mapping) or set(role.get("enum", [])) != expected_roles:
            raise ProviderSchemaError("base44_schema_role_enum_mismatch")
    else:
        verdict = properties.get("verdict")
        expected_verdicts = {
            "VERIFIED",
            "VERIFICATION_FAILED",
            "INCONCLUSIVE",
            "BLOCKED_EXTERNAL",
        }
        if not isinstance(verdict, Mapping) or set(verdict.get("enum", [])) != expected_verdicts:
            raise ProviderSchemaError("base44_schema_verdict_enum_mismatch")

    return canonical_sha256(schema)


@dataclass(frozen=True)
class Base44MirrorSnapshot:
    app_id: str
    entity_name: str
    logical_id: str
    schema_sha256: str
    record_projection_sha256: str | None
    observed_at: str

    def digest(self) -> str:
        return canonical_sha256(asdict(self))


class Base44MirrorAdapter:
    """Provider semantics around a trusted Base44 mutation transport.

    The transport may be implemented by a Base44-hosted backend or another trusted
    connector. This class owns the consequential semantics: canonical app identity,
    live schema validation, logical-ID binding, exact projection postconditions, and
    compare-before-delete compensation.
    """

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
            CANONICAL_BASE44_APP_ID,
            entity_name,
            logical_field,
            logical_id,
        )
        projection_sha = None
        if record is not None:
            projection_sha = mirror_record_hash(
                record,
                mirror_kind=entity_name,
                mirror_id=logical_id,
            )
        return Base44MirrorSnapshot(
            app_id=CANONICAL_BASE44_APP_ID,
            entity_name=entity_name,
            logical_id=logical_id,
            schema_sha256=schema_sha,
            record_projection_sha256=projection_sha,
            observed_at=datetime.now(UTC).isoformat(),
        )

    def create_exact(
        self,
        entity_name: str,
        logical_id: str,
        record: Mapping[str, Any],
    ) -> Base44MirrorSnapshot:
        expected_projection = canonical_mirror_projection(
            mirror_kind=entity_name,
            mirror_id=logical_id,
            mirror_record=record,
        )
        expected_sha = canonical_sha256(expected_projection)
        before = self.observe(entity_name, logical_id)
        if before.record_projection_sha256 is not None:
            raise RuntimeError("base44_mirror_already_exists")

        write_error: Exception | None = None
        try:
            self.transport.create_record(CANONICAL_BASE44_APP_ID, entity_name, record)
        except Exception as error:  # noqa: BLE001 - fresh read resolves provider outcome
            write_error = error

        try:
            after = self.observe(entity_name, logical_id)
        except Exception as observe_error:  # noqa: BLE001 - ambiguous provider outcome
            raise CompensationUnsafeError(
                f"base44_create_outcome_ambiguous:{type(observe_error).__name__}"
            ) from observe_error

        if after.record_projection_sha256 == expected_sha:
            return after
        if write_error is not None and after.record_projection_sha256 is None:
            raise RuntimeError("base44_create_failed_confirmed_absent") from write_error
        raise CompensationUnsafeError("base44_create_outcome_ambiguous_or_conflicting")

    def delete_exact(
        self,
        entity_name: str,
        logical_id: str,
        expected_projection_sha256: str,
    ) -> bool:
        before = self.observe(entity_name, logical_id)
        if before.record_projection_sha256 != expected_projection_sha256:
            return False
        removed = self.transport.delete_record_if_projection_matches(
            CANONICAL_BASE44_APP_ID,
            entity_name,
            _logical_id_field(entity_name),
            logical_id,
            expected_projection_sha256,
        )
        if not removed:
            return False
        after = self.observe(entity_name, logical_id)
        return after.record_projection_sha256 is None


@dataclass(frozen=True)
class ProviderAuthorityReference:
    event_id: str
    event_hash: str

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
            raise ValueError("provider saga is hard-bound to the canonical repository")
        if self.base44_entity not in _MIRROR_LOGICAL_ID_FIELD:
            raise ValueError("unsupported Base44 mirror entity")
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
    actions: Sequence[str] = ("base44.mirror.create", "github.pull_request.ready"),
    expires_at: str,
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
        (candidate for candidate in store.events() if candidate.event_id == spec.authority.event_id),
        None,
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

    expected = provider_authority_grant(
        spec,
        actions=grant.get("actions", []),
        expires_at=str(grant.get("expires_at", "")),
    )
    if set(grant) != set(expected):
        raise PermissionError("provider_authority_grant_schema_mismatch")
    for key, value in expected.items():
        if grant.get(key) != value:
            raise PermissionError(f"provider_authority_grant_mismatch:{key}")
    actions = grant.get("actions")
    if not isinstance(actions, list) or action not in actions:
        raise PermissionError(f"provider_authority_action_missing:{action}")
    expires_at = datetime.fromisoformat(str(grant["expires_at"]))
    if expires_at.tzinfo is None or now.astimezone(UTC) > expires_at.astimezone(UTC):
        raise PermissionError("provider_authority_grant_expired")

    return EvidenceRecord(
        evidence_id=f"authority:{event.event_id}:{action}",
        kind="authority",
        subject=spec.authority.identity(),
        source="canonical-event-store",
        acquired_at=now.astimezone(UTC).isoformat(),
        ttl_seconds=DEFAULT_EVIDENCE_TTL_SECONDS,
        digest=event.event_hash,
        provenance="internal",
        run_id=spec.operation_id,
        epoch=hourly_epoch(now),
    )


def _evidence(
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
        ttl_seconds=DEFAULT_EVIDENCE_TTL_SECONDS,
        digest=canonical_sha256(value),
        provenance="external",
        run_id=run_id,
        epoch=hourly_epoch(acquired_at),
    )


@dataclass(frozen=True)
class ProviderSagaResult:
    schema: str
    operation_id: str
    state: SagaState
    saga: SagaResult
    base44_proof: ProofResult | None
    github_proof: ProofResult | None
    result_digest: str
    replay_blocked: bool


class GitHubBase44ReadySaga:
    """Create an exact Base44 mirror and then make one exact GitHub PR ready.

    The Base44 row is deliberately staged before the GitHub mutation because the row is
    coordination evidence, not authority. It can therefore be safely removed if the
    GitHub pre-write proof fails. If a provider reports an ambiguous write outcome, the
    saga preserves evidence and blocks replay instead of applying a speculative rollback.
    """

    def __init__(
        self,
        *,
        event_store: EventStore,
        ledger: OperationLedger,
        github: GitHubPullRequestTransport,
        base44: Base44MirrorTransport,
    ) -> None:
        self.event_store = event_store
        self.ledger = ledger
        self.github = github
        self.base44 = Base44MirrorAdapter(base44)

    def _base44_contract(self, spec: ProviderMutationSpec) -> MutationContract:
        return MutationContract(
            operation_id=f"{spec.operation_id}:base44-stage",
            authority=spec.authority.identity(),
            actor_identity=spec.expected_base44_actor,
            target_identity=(
                f"base44:{CANONICAL_BASE44_APP_ID}/{spec.base44_entity}/"
                f"{spec.base44_logical_id}"
            ),
            preconditions=("base44_schema_pinned", "base44_mirror_absent"),
            blast_radius=1,
            rollback_plan="delete only the exact staged projection if it is still unchanged",
            postconditions=("base44_mirror_projection_exact",),
            idempotency_key=spec.idempotency_key,
            evidence_required=("authority", "identity", "target", "preconditions"),
            canary_supported=False,
        )

    def _github_contract(self, spec: ProviderMutationSpec) -> MutationContract:
        return MutationContract(
            operation_id=f"{spec.operation_id}:github-ready",
            authority=spec.authority.identity(),
            actor_identity=spec.expected_github_actor,
            target_identity=(
                f"github:{spec.repository}#pr-{spec.pull_request_number}@{spec.expected_head_sha}"
            ),
            preconditions=(
                "github_pr_open",
                "github_pr_draft",
                "github_head_exact",
                "github_base_exact",
                "base44_stage_exact",
            ),
            blast_radius=2,
            rollback_plan=(
                "preserve staged mirror on ambiguous GitHub outcome; otherwise remove exact staged "
                "mirror if GitHub action is proven not applied"
            ),
            postconditions=("github_pr_ready_exact_head",),
            idempotency_key=spec.idempotency_key,
            evidence_required=("authority", "identity", "target", "preconditions"),
            canary_supported=False,
        )

    def _prove_base44(self, spec: ProviderMutationSpec) -> ProofResult:
        started = datetime.now(UTC)
        authority = verify_provider_authority(
            self.event_store,
            spec,
            action="base44.mirror.create",
            now=started,
        )
        actor = self.base44.actor_identity()
        snapshot = self.base44.observe(spec.base44_entity, spec.base44_logical_id)
        contract = self._base44_contract(spec)
        preconditions = {
            "base44_schema_pinned": bool(snapshot.schema_sha256),
            "base44_mirror_absent": snapshot.record_projection_sha256 is None,
        }
        evidence = [
            authority,
            _evidence(
                evidence_id=f"identity:{spec.operation_id}:base44",
                kind="identity",
                subject=actor,
                source="base44",
                value={"actor": actor},
                acquired_at=started,
                run_id=spec.operation_id,
            ),
            _evidence(
                evidence_id=f"target:{spec.operation_id}:base44",
                kind="target",
                subject=contract.target_identity,
                source="base44",
                value=asdict(snapshot),
                acquired_at=started,
                run_id=spec.operation_id,
            ),
            _evidence(
                evidence_id=f"preconditions:{spec.operation_id}:base44",
                kind="preconditions",
                subject=contract.target_identity,
                source="base44",
                value=preconditions,
                acquired_at=started,
                run_id=spec.operation_id,
            ),
        ]
        return prove_mutation(
            contract,
            evidence,
            preconditions,
            now=datetime.now(UTC),
            ledger=self.ledger,
        )

    def _prove_github(self, spec: ProviderMutationSpec) -> ProofResult:
        started = datetime.now(UTC)
        authority = verify_provider_authority(
            self.event_store,
            spec,
            action="github.pull_request.ready",
            now=started,
        )
        actor = self.github.actor_identity().strip()
        snapshot = self.github.observe_pull_request(spec.repository, spec.pull_request_number)
        staged = self.base44.observe(spec.base44_entity, spec.base44_logical_id)
        expected_mirror_sha = mirror_record_hash(
            spec.base44_record,
            mirror_kind=spec.base44_entity,
            mirror_id=spec.base44_logical_id,
        )
        contract = self._github_contract(spec)
        preconditions = {
            "github_pr_open": snapshot.state == "open",
            "github_pr_draft": snapshot.draft is True,
            "github_head_exact": snapshot.head_sha == spec.expected_head_sha,
            "github_base_exact": snapshot.base_sha == spec.expected_base_sha,
            "base44_stage_exact": staged.record_projection_sha256 == expected_mirror_sha,
        }
        evidence = [
            authority,
            _evidence(
                evidence_id=f"identity:{spec.operation_id}:github",
                kind="identity",
                subject=actor,
                source="github",
                value={"actor": actor},
                acquired_at=started,
                run_id=spec.operation_id,
            ),
            _evidence(
                evidence_id=f"target:{spec.operation_id}:github",
                kind="target",
                subject=contract.target_identity,
                source="github",
                value={"github": asdict(snapshot), "base44": asdict(staged)},
                acquired_at=started,
                run_id=spec.operation_id,
            ),
            _evidence(
                evidence_id=f"preconditions:{spec.operation_id}:github",
                kind="preconditions",
                subject=contract.target_identity,
                source="github+base44",
                value=preconditions,
                acquired_at=started,
                run_id=spec.operation_id,
            ),
        ]
        return prove_mutation(
            contract,
            evidence,
            preconditions,
            now=datetime.now(UTC),
            ledger=self.ledger,
        )

    @staticmethod
    def _require_proof(proof: ProofResult, label: str) -> None:
        if not proof.passed:
            raise PermissionError(f"{label}_mutation_proof_failed:{','.join(proof.reasons)}")

    def execute(self, spec: ProviderMutationSpec) -> ProviderSagaResult:
        if self.ledger.contains(spec.idempotency_key):
            raise PermissionError("provider_saga_idempotency_key_already_committed")
        base44_proof: ProofResult | None = None
        github_proof: ProofResult | None = None
        expected_mirror_sha = mirror_record_hash(
            spec.base44_record,
            mirror_kind=spec.base44_entity,
            mirror_id=spec.base44_logical_id,
        )

        def stage_base44() -> Base44MirrorSnapshot:
            nonlocal base44_proof
            base44_proof = self._prove_base44(spec)
            self._require_proof(base44_proof, "base44")
            return self.base44.create_exact(
                spec.base44_entity,
                spec.base44_logical_id,
                spec.base44_record,
            )

        def stage_postcondition(snapshot: Base44MirrorSnapshot) -> bool:
            return snapshot.record_projection_sha256 == expected_mirror_sha

        def compensate_base44(_: Base44MirrorSnapshot) -> bool:
            return self.base44.delete_exact(
                spec.base44_entity,
                spec.base44_logical_id,
                expected_mirror_sha,
            )

        def ready_github() -> GitHubPullRequestSnapshot:
            nonlocal github_proof
            github_proof = self._prove_github(spec)
            self._require_proof(github_proof, "github")
            return self.github.set_ready(
                spec.repository,
                spec.pull_request_number,
                ready=True,
                expected_head_sha=spec.expected_head_sha,
            )

        def github_postcondition(snapshot: GitHubPullRequestSnapshot) -> bool:
            return (
                snapshot.repository == spec.repository
                and snapshot.number == spec.pull_request_number
                and snapshot.head_sha == spec.expected_head_sha
                and snapshot.base_sha == spec.expected_base_sha
                and snapshot.state == "open"
                and snapshot.draft is False
            )

        saga = SagaRunner().execute(
            [
                SagaStep(
                    name="base44-stage",
                    forward=stage_base44,
                    postcondition=stage_postcondition,
                    compensate=compensate_base44,
                    compensation_postcondition=lambda result: result is True,
                ),
                SagaStep(
                    name="github-ready",
                    forward=ready_github,
                    postcondition=github_postcondition,
                    compensate=lambda _: True,
                    compensation_postcondition=lambda result: result is True,
                ),
            ]
        )
        result_body = {
            "schema": PROVIDER_SAGA_SCHEMA,
            "operation_id": spec.operation_id,
            "idempotency_key": spec.idempotency_key,
            "state": saga.state.value,
            "saga": asdict(saga),
            "base44_proof": asdict(base44_proof) if base44_proof else None,
            "github_proof": asdict(github_proof) if github_proof else None,
            "expected_head_sha": spec.expected_head_sha,
            "expected_base_sha": spec.expected_base_sha,
            "base44_projection_sha256": expected_mirror_sha,
        }
        result_digest = canonical_sha256(result_body)
        replay_blocked = False
        if saga.state in {SagaState.COMMITTED, SagaState.COMPENSATION_FAILED, SagaState.RECOVERY_REQUIRED}:
            self.ledger.record(spec.idempotency_key, result_digest)
            replay_blocked = True
        return ProviderSagaResult(
            schema=PROVIDER_SAGA_SCHEMA,
            operation_id=spec.operation_id,
            state=saga.state,
            saga=saga,
            base44_proof=base44_proof,
            github_proof=github_proof,
            result_digest=result_digest,
            replay_blocked=replay_blocked,
        )


def default_operation_ledger(state_root: Path) -> OperationLedger:
    return OperationLedger(state_root / "control-plane" / "provider-operations.json")
