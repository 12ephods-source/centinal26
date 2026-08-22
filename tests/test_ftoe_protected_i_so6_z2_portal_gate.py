import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path('scripts/ftoe_protected_i_so6_z2_portal_gate.py')
spec = importlib.util.spec_from_file_location('portal_gate', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_z2_norm_portal_is_invariant_and_gate_fails_suppression():
    contract = json.loads(Path('research/ftoe/protected_i_so6_z2_portal_contract.json').read_text())
    result = module.evaluate(contract)
    assert result['checks']['h1_norm_z2_invariant']
    assert result['checks']['h2_norm_z2_invariant']
    assert result['checks']['norm_portal_z2_invariant']
    assert result['verdict'] == 'FAIL_Z2_ONLY_PORTAL_SUPPRESSION'
    assert result['scientific_status'] == 'FAIL_CURRENT_Z2_ONLY_SUPPRESSION_SUBGATE'


def test_scope_does_not_overclaim_general_no_go():
    contract = json.loads(Path('research/ftoe/protected_i_so6_z2_portal_contract.json').read_text())
    joined = ' '.join(contract['not_established']).lower()
    assert 'collective' in joined or 'nonlinear' in joined
    assert contract['post_result_retuning_allowed'] is False
