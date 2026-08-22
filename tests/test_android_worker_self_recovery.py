import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/termux/FROST_ANDROID_WORKER_SELF_RECOVERY_v1.0.sh"


def test_self_recovery_script_self_test():
    cp = subprocess.run(
        ["bash", str(SCRIPT), "--self-test"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "SELF_TEST PASS" in cp.stdout


def test_recovery_is_bounded_and_fail_closed():
    text = SCRIPT.read_text()
    assert "FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh" in text
    assert "repo_trusted" in text
    assert "has_noninteractive_auth" in text
    assert "AUTH_REQUIRED" in text
    assert "SOURCE_UNTRUSTED" in text
    assert "shell.exec" not in text
    assert "adb reboot" not in text
    assert "su -c" not in text
    assert "curl | bash" not in text


def test_recovery_persists_without_duplicate_processes():
    text = SCRIPT.read_text()
    assert "frost-android-worker-self-recovery --loop" in text
    assert "pgrep -f" in text
    assert "worker_running" in text
    assert "start_existing_worker" in text


def test_recovery_never_fabricates_physical_success():
    text = SCRIPT.read_text()
    forbidden = [
        'device_origin_verified":true',
        'DEPLOYED_APP_COMPLETE',
        'PROJECT_GOAL_REACHED',
        'DEVICE_VALIDATED',
    ]
    for marker in forbidden:
        assert marker not in text
