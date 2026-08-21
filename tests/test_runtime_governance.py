from __future__ import annotations

import sys
from pathlib import Path

from centinal26.agent_execution_plane import run_task
from frost_core.object_store import CanonicalObjectStore
from frost_core.objective_integrity import (
    ObjectiveIntegrityRegistry,
    ObjectiveProposal,
    ObjectiveSource,
)
from frost_core.runtime_governance import verify_runtime_objective_context


class AllowOwnerAuthorization:
    def verify(self, proposal: ObjectiveProposal) -> bool:
        return proposal.authorization_ref == "owner-auth:test"


def _authority_fixture(tmp_path: Path, *, allowed_actions: list[str] | None = None):
    store_path = tmp_path / "objects.sqlite3"
    store = CanonicalObjectStore(store_path)
    registry = ObjectiveIntegrityRegistry(
        store,
        canonical_roots=["automation_os"],
        authorization_verifier=AllowOwnerAuthorization(),
    )
    proposal = ObjectiveProposal(
        objective_id="objective:test",
        text="bounded test objective",
        source=ObjectiveSource.OWNER,
        source_ref="test-suite",
        root_objective="automation_os",
        parent_objective_id=None,
        requested_capabilities=("write:test",),
        authorization_ref="owner-auth:test",
    )
    _, evaluation_id, evaluation = registry.record(proposal)
    assert evaluation.authorization_verified is True
    authorized = store.resolve("objective/current/objective:test")
    token_id = store.put(
        "capability_token",
        {
            "task_id": "task:test",
            "objective_id": "objective:test",
            "root_objective": "automation_os",
            "allowed_actions": allowed_actions or ["write:test"],
            "network_scope": [],
            "allowed_secrets": [],
            "destructive_actions": False,
        },
        source_type="guardian",
        source_ref=authorized.object_id,
        evidence_class="CAPABILITY_AUTHORIZATION",
    )
    context = {
        "authorized_objective_id": authorized.object_id,
        "objective_evaluation_id": evaluation_id,
        "capability_token_id": token_id,
    }
    return store, store_path, context


def _task(context: dict | None = None) -> dict:
    task = {
        "task_id": "task:test",
        "role": "builder",
        "action": "write:test",
        "capabilities": [],
        "consequential": True,
        "judge_verified": True,
        "command": [sys.executable, "-c", "print('runtime-governance-pass')"],
    }
    if context is not None:
        task["objective_context"] = context
    return task


def test_runtime_gate_accepts_current_authorized_objective_and_guardian_token(tmp_path: Path):
    store, _, context = _authority_fixture(tmp_path)
    decision = verify_runtime_objective_context(store, _task(context), action_name="write:test")
    assert decision.allowed is True
    assert decision.status == "OBJECTIVE_AUTHORIZED"
    assert decision.objective_id == "objective:test"


def test_runtime_gate_rejects_scope_amplification(tmp_path: Path):
    store, _, context = _authority_fixture(tmp_path, allowed_actions=["write:other"])
    decision = verify_runtime_objective_context(store, _task(context), action_name="write:test")
    assert decision.allowed is False
    assert decision.status == "CAPABILITY_SCOPE_DENIED"


def test_runtime_gate_rejects_superseded_authorized_objective(tmp_path: Path):
    store, _, context = _authority_fixture(tmp_path)
    replacement = store.put(
        "authorized_objective",
        {
            "objective_id": "objective:test",
            "root_objective": "automation_os",
            "evaluation_object_id": "replacement-evaluation",
        },
        source_type="objective_integrity",
        source_ref="replacement-evaluation",
        evidence_class="OWNER_AUTHORIZED",
    )
    store.point("objective/current/objective:test", replacement)
    decision = verify_runtime_objective_context(store, _task(context), action_name="write:test")
    assert decision.allowed is False
    assert decision.status == "OBJECTIVE_NOT_CURRENT"


def test_execution_plane_fails_closed_without_objective_context(tmp_path: Path):
    marker = tmp_path / "must-not-exist"
    task = _task()
    task["command"] = [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"]
    result = run_task(task, tmp_path)
    assert result["status"] == "OBJECTIVE_CONTEXT_REQUIRED"
    assert not marker.exists()


def test_execution_plane_executes_only_after_runtime_objective_gate(tmp_path: Path, monkeypatch):
    _, store_path, context = _authority_fixture(tmp_path)
    monkeypatch.setenv("CENTINAL26_OBJECT_STORE", str(store_path))
    result = run_task(_task(context), tmp_path)
    assert result["status"] == "PASS"
    assert result["objective_id"] == "objective:test"
    assert "runtime-governance-pass" in result["stdout"]
