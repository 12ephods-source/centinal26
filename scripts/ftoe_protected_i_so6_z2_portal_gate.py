#!/usr/bin/env python3
import json
from pathlib import Path

CONTRACT = Path('research/ftoe/protected_i_so6_z2_portal_contract.json')
OUTPUT = Path('artifacts/ftoe_protected_i_so6_z2_portal_gate.json')


def evaluate(contract):
    frozen = contract['frozen_fields']
    h1_norm = 1
    h2_norm = (-1) * (-1)
    portal = h1_norm * h2_norm
    checks = {
        'h1_norm_z2_invariant': h1_norm == 1,
        'h2_norm_z2_invariant': h2_norm == 1,
        'norm_portal_z2_invariant': portal == 1,
        'operator_is_renormalizable_dimension4': frozen['operator_dimension'] == 4,
        'post_result_retuning_forbidden': contract['post_result_retuning_allowed'] is False,
    }
    verdict = 'FAIL_Z2_ONLY_PORTAL_SUPPRESSION' if all(checks.values()) else 'REVIEW_CONTRACT_MISMATCH'
    return {
        'gate_id': contract['gate_id'],
        'checks': checks,
        'verdict': verdict,
        'scientific_status': 'FAIL_CURRENT_Z2_ONLY_SUPPRESSION_SUBGATE' if verdict.startswith('FAIL_') else 'REVIEW',
        'interpretation': (
            'The role-separating Z2 does not forbid (H1^dagger H1)(H2^dagger H2); '
            'both scalar norms are individually invariant. This falsifies Z2-only portal suppression '
            'for this reference realization, not nonlinear/collective/sequestered suppression generally.'
        ),
        'not_established': contract['not_established'],
    }


def main():
    contract = json.loads(CONTRACT.read_text())
    result = evaluate(contract)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))
    if result['verdict'] != 'FAIL_Z2_ONLY_PORTAL_SUPPRESSION':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
