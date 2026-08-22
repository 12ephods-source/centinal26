import json
from pathlib import Path

CONTRACT = Path('research/ftoe/protected_i_so6_cw_portal_contract.json')
OUTPUT = Path('artifacts/ftoe_protected_i_so6_cw_portal_gate.json')


def evaluate(contract):
    frozen = contract['frozen_fields']
    published_term = frozen['published_potential_term']
    checks = {
        'mixed_norm_operator_explicitly_present': 'lambda3' in published_term and 'Phi1^dagger Phi1' in published_term and 'Phi2^dagger Phi2' in published_term,
        'operator_is_renormalizable_dimension4': frozen['operator_dimension'] == 4,
        'potential_is_loop_generated_reference': frozen['potential_origin'] == 'loop_generated_Coleman_Weinberg_from_explicit_SO6_breaking',
        'primary_reference_set_frozen': contract['primary_sources'] == ['arXiv:1105.5403', 'arXiv:1610.02687'],
        'successor_requires_explicit_versioning': contract['successor_allowed_only_if_versioned'] is True,
        'post_result_retuning_forbidden': contract['post_result_retuning_allowed'] is False,
    }
    verdict = (
        'FAIL_MINIMAL_REFERENCE_PORTAL_SUPPRESSION'
        if all(checks.values())
        else 'REVIEW_CONTRACT_MISMATCH'
    )
    return {
        'gate_id': contract['gate_id'],
        'checks': checks,
        'verdict': verdict,
        'scientific_status': (
            'FAIL_CURRENT_MINIMAL_SO6_REFERENCE_PORTAL_SUPPRESSION'
            if verdict.startswith('FAIL_')
            else 'REVIEW'
        ),
        'interpretation': (
            'The published minimal SO6 composite two-doublet reference potential contains the '
            'renormalizable mixed norm interaction lambda3*(Phi1^dagger Phi1)*(Phi2^dagger Phi2). '
            'Therefore the reference mechanism does not by itself establish the portal suppression '
            'required by the protected-I naturalness gate. This is candidate-specific and does not '
            'exclude separately derived composite, collective, nonlinear, or sequestered successors.'
        ),
        'not_established': contract['not_established'],
    }


def main():
    contract = json.loads(CONTRACT.read_text())
    result = evaluate(contract)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))
    if result['verdict'] != 'FAIL_MINIMAL_REFERENCE_PORTAL_SUPPRESSION':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
