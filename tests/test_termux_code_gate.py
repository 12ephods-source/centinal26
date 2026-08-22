import json
from pathlib import Path


def test_code_execution_policy_contract():
    data=json.loads(Path('automation/CODE_EXECUTION_POLICY.json').read_text())
    assert data['default_execution_plane']=='android_termux_device'
    assert data['execution_policy']['clipboard_autoexecution'] is False
    assert data['execution_policy']['run_after_qualification'] is True
    assert data['evidence']['automatic'] is True
    assert data['improvement_policy']['stop_on_plateau'] is True
    assert set(data['optimization_domains'])=={'system_automation','security','physics','faithful_user_request_completion'}


def test_code_gate_is_bounded_and_records_user_evidence():
    text=Path('termux/centinal26_code_gate.py').read_text()
    assert 'MAX_PASSES = 5' in text
    assert 'owner_class' in text and 'USER_EVIDENCE' in text
    assert 'origin_class' in text and 'ANDROID_TERMUX_DEVICE' in text
    assert 'plateau' in text
    assert 'safety_scan' in text
    assert 'qualified' in text
