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
        "evolution.evaluate_candidate",
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


def test_evolution_governor_runs_through_authorize_queue_verify_audit(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    capability = "evolution.evaluate_candidate"
    data = {
        "policy": {
            "min_occurrences": 2,
            "min_confidence": 0.90,
            "max_auto_risk": "LOW",
            "require_deterministic_pass": True,
            "require_rollback": True,
            "allow_schema_mutation": False,
            "allow_external_side_effects": False,
        },
        "envelope": {
            "capability_id": "APB-CAP-0004",
            "generation": 0,
            "maturity_score": 0.615,
            "uncertainty_score": 0.455,
            "mutation_floor": 0.01,
            "mutation_ceiling": 0.20,
            "effective_mutation_budget": 0.038295383,
            "confidence_floor": 0.93,
            "occurrence_floor": 3,
            "max_effective_risk": "LOW",
            "required_evidence_depth": 3,
            "regression_tolerances": {
                "semantic_equivalence": 0.0,
                "failure_count": 0.0,
                "rollback_available": 0.0,
            },
            "promotion_delta_min": 0.05,
            "branch_delta_min": 0.15,
            "niche_occurrence_min": 3,
            "niche_duration_days_min": 14.0,
            "niche_replication_min": 2,
            "source_meta_policy": "meta-automation-v1",
            "status": "active",
        },
        "candidate": {
            "candidate_id": "APB-EXP-0002:concurrency-4",
            "authorized": True,
            "risk_class": "LOW",
            "confidence": 0.98,
            "occurrence_count": 10,
            "evidence_depth": 1,
            "rollback_defined": True,
            "deterministic_status": None,
            "protected_deltas": {
                "semantic_equivalence": 0.0,
                "failure_count": 0.0,
                "rollback_available": 0.0,
            },
            "current_fit_deltas": {"gain": 0.6529861601078487},
            "current_fit_weights": {"gain": 1.0},
        },
    }

    job_id = runtime.submit(capability, data, grant(capability))
    assert runtime.run_once() == job_id
    assert runtime.store.counts() == {"verified": 1}
    assert runtime.audit.verify()

    row = runtime.store.connection.execute(
        "SELECT result FROM jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    result = json.loads(row["result"])
    output = result["output"]
    assert result["verification"]["passed"] is True
    assert output["promotion_authority"] is False
    assert output["decision"]["disposition"] == "REJECT_FROM_PROMOTION"
    assert output["decision"]["gate"]["disposition"] == "BLOCKED_PENDING_VALIDATION"


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
