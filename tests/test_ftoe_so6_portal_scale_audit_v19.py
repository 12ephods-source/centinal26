import importlib.util
import json
from pathlib import Path


def load_module():
    path = Path("scripts/ftoe_so6_portal_scale_audit_v19.py")
    spec = importlib.util.spec_from_file_location("portal_scale_v19", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_frozen_contract_preserves_predecessor_and_review_boundary():
    c = json.loads(Path("research/ftoe/protected_i/so6_portal_scale_audit_v19.json").read_text())
    assert c["predecessor_disposition"] == "KILLED_FOR_PROTECTED_I_ADMISSION"
    assert c["frozen_checks"]["predecessor_preserved"] is True
    assert c["frozen_checks"]["candidate_not_rehabilitated_without_composite_scale_radiative_analysis"] is True


def test_electroweak_portal_scale_is_not_gut_scale_naturalness_failure_by_presence_alone(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.chdir(Path.cwd())
    assert module.main() == 0
    result = json.loads(Path("artifacts/ftoe_so6_portal_scale_audit_v19.json").read_text())
    assert result["lambda3_one_fraction_of_mu_I_sq"] < 1e-2
    assert result["lambda3_4pi_fraction_of_mu_I_sq"] < 1e-2
    assert result["lambda3_for_delta_mu_I_sq_equal_mu_I_sq"] > 100.0
    assert result["scientific_verdict"] == "PREDECESSOR_KILL_PREMISE_INSUFFICIENT_AS_STATED__REVIEW_REQUIRED"
