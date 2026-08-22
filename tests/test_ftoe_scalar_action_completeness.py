import importlib.util
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/ftoe_scalar_action_completeness.py"
INVENTORY = ROOT / "physics/ftoe/FTOE_COMPLETE_SCALAR_ACTION_COVERAGE_2026-08-22.json"
spec = importlib.util.spec_from_file_location("ftoe_scalar_action_completeness", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _evaluate_mutation(mutate):
    payload = json.loads(INVENTORY.read_text(encoding="utf-8"))
    mutate(payload)
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "inventory.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return mod.evaluate(path)


def test_canonical_inventory_passes_execution_but_not_scientific_closure():
    result = mod.evaluate(INVENTORY)
    assert result["execution_pass"] is True
    assert result["scientific_pass"] is False
    assert result["canonical_verdict"] == "BLOCKED_COMPLETE_SCALAR_ACTION_NOT_ENUMERATED"
    assert set(result["missing_coverage_ids"]) == mod.EXPECTED_MISSING


def test_missing_sector_cannot_be_silently_removed():
    result = _evaluate_mutation(
        lambda payload: payload["required_missing_coverage"].pop()
    )
    assert result["execution_pass"] is False
    assert result["checks"]["required_missing_ids_present"] is False


def test_missing_sector_cannot_be_promoted_without_source():
    def mutate(payload):
        payload["required_missing_coverage"][0]["status"] = "ASSUMED_ZERO"

    result = _evaluate_mutation(mutate)
    assert result["execution_pass"] is False
    assert result["checks"]["missing_sectors_fail_closed"] is False


def test_pairwise_matrix_cannot_claim_action_completeness():
    def mutate(payload):
        payload["pairwise_coverage_is_sufficient_for_action_completeness"] = True
        payload["renormalizable_invariant_basis_complete"] = True
        payload["complete_action_frozen"] = True

    result = _evaluate_mutation(mutate)
    assert result["execution_pass"] is False
    assert result["checks"]["pairwise_not_sufficient"] is False
    assert result["checks"]["invariant_basis_not_complete"] is False
    assert result["checks"]["action_not_frozen"] is False


def test_invented_coupling_values_fail_closed():
    def mutate(payload):
        payload["invented_coupling_values"] = [{"name": "lambda_unknown", "value": 1.0}]

    result = _evaluate_mutation(mutate)
    assert result["execution_pass"] is False
    assert result["checks"]["no_invented_couplings"] is False
