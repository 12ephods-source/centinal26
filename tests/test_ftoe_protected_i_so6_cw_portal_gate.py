import json
from pathlib import Path

from scripts.ftoe_protected_i_so6_cw_portal_gate import evaluate


def load_contract():
    return json.loads(Path('research/ftoe/protected_i_so6_cw_portal_contract.json').read_text())


def test_minimal_reference_contains_mixed_norm_portal():
    result = evaluate(load_contract())
    assert result['verdict'] == 'FAIL_MINIMAL_REFERENCE_PORTAL_SUPPRESSION'
    assert result['scientific_status'] == 'FAIL_CURRENT_MINIMAL_SO6_REFERENCE_PORTAL_SUPPRESSION'
    assert all(result['checks'].values())


def test_scope_remains_candidate_specific_and_fail_closed():
    contract = load_contract()
    assert contract['post_result_retuning_allowed'] is False
    assert contract['successor_allowed_only_if_versioned'] is True
    assert 'a no-go theorem against all composite, collective, nonlinear, or sequestered portal suppression mechanisms' in contract['not_established']
    assert 'publication readiness' in contract['not_established']
