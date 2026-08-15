from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from frost_core.fleet_controller import FleetController, rank_contract


def make_contract(ctl, key, role="BUILDER", priority="P1", deps=None,
                  on_verified_role=None, subsystem="core"):
    return ctl.create_contract(
        idempotency_key=key,
        problem_statement=f"solve {key}",
        source_basis={"source": "test"},
        priority=priority,
        expected_outcome="closed",
        success_criteria=["test passes"],
        allowed_scope=["tests"],
        prohibited_scope=["security policy"],
        dependencies=deps or [],
        assigned_role=role,
        verification_requirements=["independent check"],
        rollback_plan={"type": "revert"},
        resource_budget={"max_files": 4},
        retry_budget=2,
        current_head="abc",
        subsystem=subsystem,
        failure_criteria=["regression"],
        next_review_condition="result",
        ranking={"downstream_leverage": 0.8, "execution_readiness": 0.9},
        on_verified_role=on_verified_role,
        now=datetime(2026, 8, 15, tzinfo=UTC),
    )


def test_contract_dedupe_and_priority(tmp_path):
    ctl = FleetController(tmp_path / "state.sqlite3")
    try:
        first = make_contract(ctl, "same", priority="P1")
        second = make_contract(ctl, "same", priority="P0")
        assert first["created"] is True
        assert second["created"] is False
        assert rank_contract("P0") > rank_contract("P1")
        assert ctl.verify_event_chain()
    finally:
        ctl.close()


def test_builder_to_judge_to_sre_handoff(tmp_path):
    ctl = FleetController(tmp_path / "state.sqlite3")
    try:
        contract = make_contract(ctl, "pipeline", on_verified_role="SRE")
        claimed = ctl.claim_next("BUILDER", claimer="builder")
        assert [item["contract_id"] for item in claimed] == [contract["contract_id"]]
        result = ctl.record_result(
            contract["contract_id"], role="BUILDER",
            status="EXECUTED_AWAITING_VERIFICATION",
            payload={"tests": "PASS"}, evidence_hash="e" * 64,
        )
        pending = ctl.pending_verification()
        assert pending[0]["result_id"] == result["result_id"]
        judge_claim = ctl.claim_next("JUDGE", claimer="judge")
        assert judge_claim[0]["contract_id"] == contract["contract_id"]
        verdict = ctl.record_verdict(
            result["result_id"], verdict="VERIFIED", verifier="judge-v1",
            details={"independent": True}, evidence_hash="v" * 64,
        )
        assert verdict["verdict"] == "VERIFIED"
        sre_claim = ctl.claim_next("SRE", claimer="sre")
        assert sre_claim[0]["contract_id"] == contract["contract_id"]
        assert ctl.verify_event_chain()
    finally:
        ctl.close()


def test_dependencies_block_until_verified(tmp_path):
    ctl = FleetController(tmp_path / "state.sqlite3")
    try:
        dep = make_contract(ctl, "dep", role="JUDGE")
        child = make_contract(ctl, "child", deps=[dep["contract_id"]])
        assert ctl.claim_next("BUILDER", claimer="b") == []
        ctl.record_result(dep["contract_id"], role="JUDGE", status="VERIFIED", payload={"ok": True})
        claimed = ctl.claim_next("BUILDER", claimer="b")
        assert claimed[0]["contract_id"] == child["contract_id"]
    finally:
        ctl.close()


def test_lease_recovery_and_retry_budget(tmp_path):
    ctl = FleetController(tmp_path / "state.sqlite3")
    try:
        make_contract(ctl, "lease")
        t0 = datetime(2026, 8, 15, tzinfo=UTC)
        assert ctl.claim_next("BUILDER", claimer="a", lease_seconds=10, now=t0)
        assert ctl.claim_next("BUILDER", claimer="b", now=t0 + timedelta(seconds=5)) == []
        recovered = ctl.claim_next("BUILDER", claimer="b", now=t0 + timedelta(seconds=11))
        assert recovered[0]["claimed_by"] == "b"
    finally:
        ctl.close()


def test_error_budget_contracts_builder_subsystem(tmp_path):
    ctl = FleetController(tmp_path / "state.sqlite3")
    try:
        contract = make_contract(ctl, "risky", subsystem="provider")
        now = datetime(2026, 8, 15, tzinfo=UTC)
        for idx in range(4):
            ctl.record_error_event(
                subsystem="provider", event_type="RECOVERY_FAILURE", severity="HIGH",
                recovered=idx >= 2, details={"i": idx}, now=now + timedelta(minutes=idx),
            )
        budget = ctl.error_budget("provider", now=now + timedelta(minutes=5))
        assert budget["contracted"] is True
        assert ctl.claim_next("BUILDER", claimer="builder", now=now + timedelta(minutes=5)) == []
        assert ctl.status()["metrics"]["contracts_total"] == 1
        assert contract["contract_id"]
    finally:
        ctl.close()


def test_append_only_event_log_and_metrics(tmp_path):
    ctl = FleetController(tmp_path / "state.sqlite3")
    try:
        contract = make_contract(ctl, "metrics", role="SRE")
        ctl.claim_next("SRE", claimer="sre")
        ctl.record_result(contract["contract_id"], role="SRE", status="OPERATIONAL",
                          payload={"health": "PASS"})
        metrics = ctl.metrics(persist=True)
        assert metrics["solved"] == 1
        assert metrics["event_chain_valid"] is True
        with pytest.raises(Exception):
            ctl.db.execute("UPDATE fleet_event_log SET event_type='tampered' WHERE seq=1")
    finally:
        ctl.close()
