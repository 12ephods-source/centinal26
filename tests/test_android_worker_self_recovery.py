from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/termux/FROST_ANDROID_WORKER_SELF_RECOVERY_v1.0.sh"


def _env(tmp_path: Path, *, termux: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["CENTINAL26_ROOT"] = str(tmp_path / "repo")
    env["AUTOMATION_BRIDGE_ROOT"] = str(tmp_path / "bridge")
    env["FROST_WORKER_RECOVERY_STATE"] = str(tmp_path / "state")
    env["BASE44_TOKEN"] = "test-token"
    env["BASE44_WORKER_EMAIL"] = "worker@example.invalid"
    if termux:
        env["PREFIX"] = "/data/data/com.termux/files/usr"
    else:
        env.pop("PREFIX", None)
    return env


def _status(tmp_path: Path) -> dict[str, object]:
    path = tmp_path / "state" / "status.json"
    return json.loads(path.read_text(encoding="utf-8"))


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
        'device_origin_verified\":true',
        "DEPLOYED_APP_COMPLETE",
        "PROJECT_GOAL_REACHED",
        "DEVICE_VALIDATED",
    ]
    for marker in forbidden:
        assert marker not in text


def test_recovery_fails_closed_outside_termux(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--once"],
        env=_env(tmp_path, termux=False),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 40
    assert _status(tmp_path)["state"] == "NOT_TERMUX"


def test_recovery_preserves_untrusted_source_failure_code(tmp_path: Path) -> None:
    # A Termux-shaped environment with no trusted repository must preserve the
    # repo_trusted() failure code rather than allowing Bash `if` semantics to
    # collapse it to a successful process exit.
    result = subprocess.run(
        ["bash", str(SCRIPT), "--once"],
        env=_env(tmp_path, termux=True),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 31
    status = _status(tmp_path)
    assert status["state"] == "SOURCE_UNTRUSTED"
    assert "identity" in str(status["detail"]).lower()
