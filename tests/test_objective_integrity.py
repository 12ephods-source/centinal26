from __future__ import annotations

from frost_core.objective_integrity import (
    Action,
    CapabilityToken,
    ObjectiveDecision,
    ObjectiveIntegrityRegistry,
    ObjectiveProposal,
    ObjectiveSource,
    child_capabilities_valid,
    execution_gate,
)


class FakeStore:
    def __init__(self):
        self.objects = {}
        self.links = []
        self.aliases = {}
        self.n = 0

    def put(self, kind, payload, **provenance):
        self.n += 1
        oid = f"o{self.n}"
        self.objects[oid] = {
            "kind": kind,
            "payload": payload,
            "provenance": provenance,
        }
        return oid

    def link(self, parent_id, relation, child_id):
        self.links.append((parent_id, relation, child_id))

    def point(self, alias, object_id, **kwargs):
        self.aliases[alias] = object_id


class TestVerifier:
    def verify(self, proposal):
        return proposal.authorization_ref == "owner:signed:test"


ROOTS = {"automation_os", "frost_learning_os", "sdos_verification", "physics_research"}


def registry():
    return ObjectiveIntegrityRegistry(
        FakeStore(),
        canonical_roots=ROOTS,
        authorization_verifier=TestVerifier(),
    )


def test_remote_agent_can_only_propose():
    r = registry()
    p = ObjectiveProposal(
        objective_id="open_source_inventory",
        text="Evaluate A2A and MCP",
        source=ObjectiveSource.REMOTE_AGENT,
        source_ref="agent:remote:1",
        root_objective="automation_os",
        parent_objective_id=None,
        requested_capabilities=("read_repo",),
        authorization_ref="owner:signed:test",
    )
    assert r.evaluate(p).decision == ObjectiveDecision.PROPOSE_ONLY


def test_owner_without_verified_signature_is_quarantined():
    r = registry()
    p = ObjectiveProposal(
        objective_id="automation_os",
        text="Protect objective integrity",
        source=ObjectiveSource.OWNER,
        source_ref="owner-channel",
        root_objective="automation_os",
        parent_objective_id=None,
        requested_capabilities=("read_repo",),
        authorization_ref="invalid",
    )
    assert r.evaluate(p).decision == ObjectiveDecision.QUARANTINE


def test_owner_verified_canonical_objective_executes_and_is_aliased():
    r = registry()
    p = ObjectiveProposal(
        objective_id="automation_os",
        text="Protect objective integrity",
        source=ObjectiveSource.OWNER,
        source_ref="owner-channel",
        root_objective="automation_os",
        parent_objective_id=None,
        requested_capabilities=("read_repo", "run_tests"),
        authorization_ref="owner:signed:test",
    )
    _, _, decision = r.record(p)
    assert decision.decision == ObjectiveDecision.EXECUTE
    assert "objective/current/automation_os" in r.store.aliases


def test_unknown_root_is_quarantined():
    r = registry()
    p = ObjectiveProposal(
        objective_id="new_root",
        text="Create a new mission",
        source=ObjectiveSource.OWNER,
        source_ref="owner-channel",
        root_objective="not_canonical",
        parent_objective_id=None,
        authorization_ref="owner:signed:test",
    )
    assert r.evaluate(p).decision == ObjectiveDecision.QUARANTINE


def test_forbidden_capability_is_denied():
    r = registry()
    p = ObjectiveProposal(
        objective_id="automation_os",
        text="Unsafe expansion",
        source=ObjectiveSource.OWNER,
        source_ref="owner-channel",
        root_objective="automation_os",
        parent_objective_id=None,
        requested_capabilities=("credential_export",),
        authorization_ref="owner:signed:test",
    )
    assert r.evaluate(p).decision == ObjectiveDecision.DENY


def test_capability_non_amplification_and_execution_scope():
    parent = CapabilityToken(
        task_id="p",
        objective_id="automation_os",
        root_objective="automation_os",
        allowed_actions=frozenset({"read_repo", "run_tests"}),
        network_scope=frozenset({"github.com"}),
    )
    child = CapabilityToken(
        task_id="c",
        objective_id="automation_os",
        root_objective="automation_os",
        allowed_actions=frozenset({"read_repo"}),
        network_scope=frozenset({"github.com"}),
    )
    amplified = CapabilityToken(
        task_id="x",
        objective_id="automation_os",
        root_objective="automation_os",
        allowed_actions=frozenset({"read_repo", "credential_export"}),
        network_scope=frozenset({"github.com"}),
    )
    assert child_capabilities_valid(parent, child)
    assert not child_capabilities_valid(parent, amplified)
    assert execution_gate(
        child,
        Action(name="read_repo", destination="github.com", requires_network=True),
    )
    assert not execution_gate(
        child,
        Action(name="read_repo", destination="evil.example", requires_network=True),
    )
