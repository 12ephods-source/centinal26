from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMUX = ROOT / "termux"


def run_bash(script: str, *, home: Path, extra_env: dict[str, str] | None = None):
    env = os.environ.copy()
    env["HOME"] = str(home)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_runtime_config_serializes_metadata_as_json_and_never_persists_token(tmp_path: Path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1 $2 $3\" = \"auth token --hostname\" ]; then echo test-token; exit 0; fi\n"
        "if [ \"$1 $2\" = \"auth token\" ]; then echo test-token; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh.chmod(0o700)
    config = tmp_path / "config.json"
    helper = TERMUX / "github_runtime_config.sh"
    command = f'''
set -euo pipefail
source "{helper}"
github_runtime_write_config "{config}" "12ephods-source/centinal26" main "android-aarch64-123"
github_runtime_load_config "{config}"
printf '%s|%s|%s|%s\n' "$GITHUB_REPO" "$GITHUB_REF" "$AUTOMATION_DEVICE_ID" "$GITHUB_TOKEN"
'''
    result = run_bash(command, home=tmp_path, extra_env={"PATH": f"{bindir}:{os.environ['PATH']}"})
    assert result.returncode == 0, result.stdout
    assert "12ephods-source/centinal26|main|android-aarch64-123|test-token" in result.stdout
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data == {
        "schema": "centinal26-github-worker-config-v1",
        "github_repo": "12ephods-source/centinal26",
        "github_ref": "main",
        "automation_device_id": "android-aarch64-123",
    }
    assert "token" not in config.read_text(encoding="utf-8").lower()


def test_runtime_config_rejects_noncanonical_repo_and_injection_shaped_device_id(tmp_path: Path):
    helper = TERMUX / "github_runtime_config.sh"
    config = tmp_path / "config.json"
    noncanonical = run_bash(
        f'source "{helper}"; github_runtime_write_config "{config}" "evil/repo" main device',
        home=tmp_path,
    )
    assert noncanonical.returncode != 0
    assert "BLOCKED_NONCANONICAL_REPO" in noncanonical.stdout

    injected = run_bash(
        f'''source "{helper}"; github_runtime_write_config "{config}" "12ephods-source/centinal26" main 'device$(touch /tmp/should-not-run)' ''',
        home=tmp_path,
    )
    assert injected.returncode != 0
    assert "BLOCKED_INVALID_DEVICE_ID" in injected.stdout
    assert not Path("/tmp/should-not-run").exists()


def test_termux_workers_do_not_source_mutable_runtime_config():
    for relative in (
        "github_termux_worker_once.sh",
        "report_after_reboot.sh",
        "intelligence_controller_github_worker_once.sh",
        "intelligence_controller_report_after_reboot.sh",
    ):
        text = (TERMUX / relative).read_text(encoding="utf-8")
        assert '/.automation_os_github/config"' not in text
        assert 'source "$CONFIG"' not in text
        assert "github_runtime_load_config" in text


def test_installers_do_not_persist_github_token():
    for relative in ("install_github_control.sh", "install_intelligence_github_control.sh"):
        text = (TERMUX / relative).read_text(encoding="utf-8")
        assert 'GITHUB_TOKEN="$TOKEN"' not in text
        assert "github_runtime_write_config" in text
        assert 'rm -f "$CFGDIR/config"' in text


def test_untrusted_candidate_auditor_has_no_flag_only_review_override():
    text = (ROOT / "scripts" / "audit_untrusted_candidate.py").read_text(encoding="utf-8")
    assert "--allow-reviewed-risk" not in text
    assert "EXPLICIT_REVIEW_OVERRIDE" not in text
    assert 'report["decision"] == "ALLOW_STATIC_ONLY"' in text
