import json
from datetime import UTC, datetime, timedelta

from centinal26.core import AuditLog, Engine, Grant, JobStore
from centinal26.future import register_future_capabilities


def make_runtime(tmp_path) -> Engine:
    runtime = Engine(
        JobStore(tmp_path / "queue.sqlite3"),
        AuditLog(tmp_path / "audit.jsonl"),
    )
    register_future_capabilities(runtime)
    return runtime


def grant(capability: str) -> Grant:
    return Grant(
        grant_id="future-test",
        capability=capability,
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )


def test_future_capabilities_are_registered_but_hard_gates_are_not(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    assert set(runtime.capabilities) == {
        "cognition.intelligence_awareness",
        "cognition.predictive_attention",
        "cognition.delegated_route",
        "cognition.strategic_forecast",
        "system.future_capabilities",
    }
    assert "cognition.adversarial_candidate_execution" not in runtime.capabilities
    assert "system.autonomous_main_promotion" not in runtime.capabilities


def test_predictive_attention_runs_through_authorize_queue_verify_audit(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    capability = "cognition.predictive_attention"
    data = {
        "signal": {
            "signal_id": "deadline",
            "urgency": 0.95,
            "impact": 0.90,
            "confidence": 0.90,
            "novelty": 0.30,
            "reversibility": 0.10,
            "interruption_cost": 0.20,
            "deadline_hours": 1.0,
        }
    }

    job_id = runtime.submit(capability, data, grant(capability))
    assert runtime.store.counts() == {"queued": 1}
    assert runtime.run_once() == job_id
    assert runtime.store.counts() == {"verified": 1}
    assert runtime.audit.verify()

    row = runtime.store.connection.execute(
        "SELECT result FROM jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    result = json.loads(row["result"])
    assert result["verification"]["passed"] is True
    assert result["output"]["action"] == "INTERRUPT"


def test_wrong_grant_cannot_invoke_future_capability(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    wrong_grant = grant("cognition.intelligence_awareness")
    data = {
        "signal": {
            "signal_id": "noise",
            "urgency": 0.05,
            "impact": 0.05,
            "confidence": 0.90,
            "novelty": 0.10,
            "reversibility": 1.0,
            "interruption_cost": 0.90,
        }
    }

    try:
        runtime.submit("cognition.predictive_attention", data, wrong_grant)
    except PermissionError:
        pass
    else:
        raise AssertionError("mismatched grant must be denied")

    assert runtime.store.counts() == {}
    assert runtime.audit.verify()
