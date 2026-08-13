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


def dragon_input() -> dict:
    return {
        "meta_policy": {
            "min_occurrences": 2,
            "min_confidence": 0.90,
            "max_auto_risk": "LOW",
            "require_deterministic_pass": True,
            "require_rollback": True,
            "allow_schema_mutation": False,
            "allow_external_side_effects": False,
        },
        "kernel_policy": {
            "maturity_weights": {
                "validation_stability": 0.25,
                "regression_resilience": 0.20,
                "environment_coverage": 0.15,
                "rollback_readiness": 0.15,
                "repeated_success": 0.15,
                "promotion_closure": 0.10,
            },
            "uncertainty_weights": {
                "evidence_gap": 0.35,
                "environment_gap": 0.30,
                "model_error": 0.20,
                "frontier_opportunity": 0.15,
            },
            "mutation_floor": 0.01,
            "mutation_ceiling": 0.20,
            "annealing_rate": 2.0,
            "exploration_floor_fraction": 0.10,
            "confidence_floor": 0.93,
            "occurrence_floor": 3,
            "required_evidence_depth": 3,
            "regression_tolerances": {
                "semantic_equivalence": 0.0,
                "failure_count": 0.0,
                "rollback_available": 0.0,
            },
            "promotion_delta_min": 0.05,
            "branch_delta_min": 0.15,
            "niche_occurrence_min": 3,
            "niche_duration_min_days": 14.0,
            "niche_replication_min": 2,
            "max_effective_risk": "LOW",
        },
        "seed": {
            "capability_id": "APB-CAP-0004",
            "generation": 0,
            "maturity_components": {
                "validation_stability": 0.75,
                "regression_resilience": 0.70,
                "environment_coverage": 0.25,
                "rollback_readiness": 1.00,
                "repeated_success": 0.50,
                "promotion_closure": 0.25,
            },
            "uncertainty_components": {
                "evidence_gap": 0.50,
                "environment_gap": 0.75,
                "model_error": 0.10,
                "frontier_opportunity": 0.23333333333333334,
            },
            "source_meta_policy": "meta-automation-v1",
            "source_policy_hash": (
                "87a0074a844ee9a65bedc8f5d43c08767dec88964655936fa75e230ee43b5e9f"
            ),
            "source_evidence_hash": (
                "a793e41012759884a47487f0451438db036a23b21797453356ca74b826d0c888"
            ),
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
            "schema_mutation": False,
            "external_side_effects": False,
            "protected_deltas": {
                "semantic_equivalence": 0.0,
                "failure_count": 0.0,
                "rollback_available": 0.0,
            },
            "current_fit_deltas": {
                "wall_clock_reduction": 0.6529861601078487,
                "semantic_delta": 0.0,
                "failure_delta": 0.0,
                "calibration_delta": -0.09317254513433963,
            },
            "current_fit_weights": {
                "wall_clock_reduction": 0.65,
                "semantic_delta": 0.20,
                "failure_delta": 0.10,
                "calibration_delta": 0.05,
            },
            "niche_fit_deltas": {"niche_gain": 0.0},
            "niche_fit_weights": {"niche_gain": 1.0},
            "persistence": {
                "independent_occurrences": 1,
                "duration_days": 0.0,
                "independent_replications": 1,
                "median_advantage": 0.0,
            },
            "low_switching_cost": False,
            "high_coexistence_cost": False,
        },
    }


def test_evolution_governor_runs_through_authorize_queue_verify_audit(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    capability = "evolution.evaluate_candidate"
    job_id = runtime.submit(capability, dragon_input(), grant(capability))

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
    assert output["envelope"]["maturity_score"] == 0.615
    assert output["decision"]["decision"] == "REJECT_FROM_PROMOTION"
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
