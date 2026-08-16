from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from centinal26.control_plane import OperationLedger
from centinal26.event_state import EventStore
from centinal26.mirror_evidence import mirror_record_hash
from centinal26.provider_bridge import (
    CANONICAL_BASE44_APP_ID,
    CANONICAL_REPOSITORY,
    Base44MirrorTransport,
    GitHubBase44ReadyBridge,
    GitHubPullRequestSnapshot,
    ProviderAuthorityReference,
    ProviderBridgeState,
    ProviderMutationSpec,
    ProviderOutcomeAmbiguous,
    provider_authority_grant,
    validate_base44_mirror_schema,
)

NOW = datetime(2026, 8, 16, 10, 0, tzinfo=UTC)
HEAD = "a" * 40
BASE = "b" * 40


def _schema() -> dict[str, Any]:
    properties = {
        "result_id": {"type": "string"},
        "contract_id": {"type": "string"},
        "role": {
            "type": "string",
            "enum": ["GOVERNOR", "BUILDER", "JUDGE", "SRE", "EVOLUTION"],
        },
        "status": {"type": "string"},
        "payload_json": {"type": "string"},
        "evidence_hash": {"type": "string"},
        "result_hash": {"type": "string"},
        "created_at_client": {"type": "string"},
    }
    admin = {"user_condition": {"role": "admin"}}
    return {
        "name": "AutomationRoleResult",
        "type": "object",
        "properties": properties,
        "required": [
            "result_id",
            "contract_id",
            "role",
            "status",
            "payload_json",
            "result_hash",
            "created_at_client",
        ],
        "rls": {
            "create": admin,
            "read": admin,
            "update": admin,
            "delete": admin,
        },
    }


def _record(**overrides: Any) -> dict[str, Any]:
    value = {
        "result_id": "result:provider-bridge:test",
        "contract_id": "contract:provider-bridge:test",
        "role": "SRE",
        "status": "EXECUTED_AWAITING_VERIFICATION",
        "payload_json": '{"pr":85,"action":"ready"}',
        "evidence_hash": "c" * 64,
        "result_hash": "d" * 64,
        "created_at_client": "2026-08-16T04:00:00-06:00",
    }
    value.update(overrides)
    return value


class FakeBase44(Base44MirrorTransport):
    def __init__(self) -> None:
        self.schema = _schema()
        self.record: dict[str, Any] | None = None
        self.actor = "base44:admin:control-plane"
        self.delete_calls = 0

    def actor_identity(self) -> str:
        return self.actor

    def observe_schema(self, app_id: str, entity_name: str) -> dict[str, Any]:
        assert app_id == CANONICAL_BASE44_APP_ID
        assert entity_name == "AutomationRoleResult"
        return self.schema

    def observe_record(
        self,
        app_id: str,
        entity_name: str,
        logical_id_field: str,
        logical_id: str,
    ) -> dict[str, Any] | None:
        assert app_id == CANONICAL_BASE44_APP_ID
        assert entity_name == "AutomationRoleResult"
        assert logical_id_field == "result_id"
        if self.record is None or self.record[logical_id_field] != logical_id:
            return None
        return dict(self.record)

    def create_record(
        self,
        app_id: str,
        entity_name: str,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        assert app_id == CANONICAL_BASE44_APP_ID
        assert entity_name == "AutomationRoleResult"
        if self.record is not None:
            raise RuntimeError("duplicate")
        self.record = {
            **record,
            "id": "base44-row-1",
            "created_date": "2026-08-16T10:00:00Z",
            "updated_date": "2026-08-16T10:00:00Z",
            "created_by_id": "admin-1",
            "is_sample": False,
        }
        return dict(self.record)

    def delete_record_if_projection_matches(
        self,
        app_id: str,
        entity_name: str,
        logical_id_field: str,
        logical_id: str,
        expected_projection_sha256: str,
    ) -> bool:
        self.delete_calls += 1
        current = self.observe_record(
            app_id, entity_name, logical_id_field, logical_id
        )
        if current is None:
            return False
        actual = mirror_record_hash(
            current,
            mirror_kind=entity_name,
            mirror_id=logical_id,
        )
        if actual != expected_projection_sha256:
            return False
        self.record = None
        return True


class FakeGitHub:
    def __init__(self, base44: FakeBase44) -> None:
        self.base44 = base44
        self.actor = "github:12ephods-source"
        self.head = HEAD
        self.base = BASE
        self.draft = True
        self.state = "open"
        self.mode = "success"
        self.mutate_base44_on_identity = False
        self.set_ready_calls = 0

    def actor_identity(self) -> str:
        if self.mutate_base44_on_identity and self.base44.record is not None:
            self.base44.record["status"] = "CONCURRENTLY_EDITED"
        return self.actor

    def observe_pull_request(
        self, repository: str, number: int
    ) -> GitHubPullRequestSnapshot:
        assert repository == CANONICAL_REPOSITORY
        return GitHubPullRequestSnapshot(
            repository=repository,
            number=number,
            node_id="PR_node_85",
            head_sha=self.head,
            base_sha=self.base,
            state=self.state,
            draft=self.draft,
            observed_at=NOW.isoformat(),
        )

    def set_ready(
        self,
        repository: str,
        number: int,
        *,
        ready: bool,
        expected_head_sha: str,
    ) -> GitHubPullRequestSnapshot:
        self.set_ready_calls += 1
        if self.head != expected_head_sha:
            raise RuntimeError("head changed")
        if self.mode == "fail_before_apply":
            raise RuntimeError("confirmed provider failure")
        self.draft = not ready
        if self.mode == "ambiguous_after_apply":
            raise ProviderOutcomeAmbiguous("simulated ambiguous response")
        return self.observe_pull_request(repository, number)


def _provisional_spec(record: dict[str, Any]) -> ProviderMutationSpec:
    return ProviderMutationSpec(
        operation_id="op:provider-bridge:test",
        idempotency_key="idem:provider-bridge:test",
        repository=CANONICAL_REPOSITORY,
        pull_request_number=85,
        expected_head_sha=HEAD,
        expected_base_sha=BASE,
        base44_entity="AutomationRoleResult",
        base44_logical_id=record["result_id"],
        base44_record=record,
        expected_github_actor="github:12ephods-source",
        expected_base44_actor="base44:admin:control-plane",
        authority=ProviderAuthorityReference("authority-event", "0" * 64),
    )


def _authorized_spec(
    store: EventStore,
    record: dict[str, Any],
    *,
    expires_at: datetime | None = None,
    actions: tuple[str, ...] = (
        "base44.mirror.create",
        "github.pull_request.ready",
    ),
) -> ProviderMutationSpec:
    provisional = _provisional_spec(record)
    grant = provider_authority_grant(
        provisional,
        expires_at=(expires_at or NOW + timedelta(minutes=5)).isoformat(),
        actions=actions,
    )
    event = store.append(
        "DECISION_RECORDED",
        {"provider_mutation_grant": grant, "decision": "allow"},
        entity_id=provisional.operation_id,
        event_id="authority-event",
        ts=NOW.isoformat(),
    )
    return replace(
        provisional,
        authority=ProviderAuthorityReference(event.event_id, event.event_hash),
    )


def _bridge(
    tmp_path: Path,
    store: EventStore,
    github: FakeGitHub,
    base44: FakeBase44,
) -> GitHubBase44ReadyBridge:
    return GitHubBase44ReadyBridge(
        event_store=store,
        ledger=OperationLedger(tmp_path / "provider-ledger.json"),
        github=github,
        base44=base44,
        clock=lambda: NOW,
    )


def test_live_base44_schema_shape_is_accepted() -> None:
    assert len(validate_base44_mirror_schema("AutomationRoleResult", _schema())) == 64


def test_wrong_base44_rls_is_rejected() -> None:
    schema = _schema()
    schema["rls"]["create"] = {"user_condition": {"role": "user"}}
    with pytest.raises(ValueError, match="base44_schema_rls_mismatch:create"):
        validate_base44_mirror_schema("AutomationRoleResult", schema)


def test_happy_path_stages_mirror_then_marks_exact_pr_ready(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    base44 = FakeBase44()
    github = FakeGitHub(base44)
    record = _record()
    spec = _authorized_spec(store, record)
    bridge = _bridge(tmp_path, store, github, base44)

    result = bridge.execute(spec)

    assert result.state is ProviderBridgeState.COMMITTED
    assert github.draft is False
    assert github.set_ready_calls == 1
    assert base44.record is not None
    assert result.base44_proof is not None and result.base44_proof.passed
    assert result.github_proof is not None and result.github_proof.passed
    assert result.replay_blocked is True


def test_actor_identity_mismatch_blocks_before_base44_write(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    base44 = FakeBase44()
    base44.actor = "base44:admin:unexpected"
    github = FakeGitHub(base44)
    spec = _authorized_spec(store, _record())

    result = _bridge(tmp_path, store, github, base44).execute(spec)

    assert result.state is ProviderBridgeState.COMPENSATED
    assert base44.record is None
    assert github.set_ready_calls == 0
    assert result.base44_proof is not None
    assert "evidence_subject_mismatch:identity" in result.base44_proof.reasons


def test_expired_canonical_authority_blocks_all_provider_writes(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    base44 = FakeBase44()
    github = FakeGitHub(base44)
    spec = _authorized_spec(store, _record(), expires_at=NOW - timedelta(seconds=1))

    result = _bridge(tmp_path, store, github, base44).execute(spec)

    assert result.state is ProviderBridgeState.COMPENSATED
    assert "provider_authority_grant_expired" in (result.saga.error or "")
    assert base44.record is None
    assert github.set_ready_calls == 0


def test_missing_github_action_in_grant_compensates_staged_mirror(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    base44 = FakeBase44()
    github = FakeGitHub(base44)
    spec = _authorized_spec(store, _record(), actions=("base44.mirror.create",))

    result = _bridge(tmp_path, store, github, base44).execute(spec)

    assert result.state is ProviderBridgeState.COMPENSATED
    assert result.saga.compensated == ("base44-stage",)
    assert base44.record is None
    assert github.set_ready_calls == 0


def test_live_github_head_drift_compensates_staged_mirror(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    base44 = FakeBase44()
    github = FakeGitHub(base44)
    spec = _authorized_spec(store, _record())
    github.head = "e" * 40

    result = _bridge(tmp_path, store, github, base44).execute(spec)

    assert result.state is ProviderBridgeState.COMPENSATED
    assert result.github_proof is not None
    assert "precondition_failed:github_head_exact" in result.github_proof.reasons
    assert base44.record is None
    assert github.set_ready_calls == 0


def test_ambiguous_github_outcome_preserves_mirror_and_blocks_replay(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    base44 = FakeBase44()
    github = FakeGitHub(base44)
    github.mode = "ambiguous_after_apply"
    spec = _authorized_spec(store, _record())
    bridge = _bridge(tmp_path, store, github, base44)

    result = bridge.execute(spec)

    assert result.state is ProviderBridgeState.RECOVERY_REQUIRED
    assert result.saga.compensated == ()
    assert base44.record is not None
    assert github.draft is False
    assert result.replay_blocked is True
    with pytest.raises(PermissionError, match="provider_bridge_replay_blocked"):
        bridge.execute(spec)


def test_concurrent_mirror_edit_prevents_destructive_compensation(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    base44 = FakeBase44()
    github = FakeGitHub(base44)
    github.mutate_base44_on_identity = True
    spec = _authorized_spec(store, _record())

    result = _bridge(tmp_path, store, github, base44).execute(spec)

    assert result.state is ProviderBridgeState.COMPENSATION_FAILED
    assert base44.record is not None
    assert base44.record["status"] == "CONCURRENTLY_EDITED"
    # The adapter detects projection drift locally and refuses to invoke the provider
    # delete at all, which is stronger than asking the provider to reject it.
    assert base44.delete_calls == 0
    assert result.replay_blocked is True


def test_wrong_repository_is_rejected_before_execution() -> None:
    with pytest.raises(ValueError, match="hard-bound"):
        replace(_provisional_spec(_record()), repository="other/repository")
