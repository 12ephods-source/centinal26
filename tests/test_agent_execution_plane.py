import subprocess
from pathlib import Path

from centinal26.agent_execution_plane import authorize_task, run_task


def test_pass(tmp_path: Path):
    result = run_task(
        {"role": "builder", "command": ["python", "-c", "print('ok')"]},
        tmp_path,
    )
    assert result["status"] == "PASS" and "ok" in result["stdout"]
    assert result["action"] == "execute:bounded_task"
    assert result["evidence_digest"]


def test_root_deny_preserves_legacy_alias(tmp_path: Path):
    result = run_task(
        {
            "role": "sre",
            "capabilities": ["credential_root"],
            "command": ["python", "-c", "print('bad')"],
        },
        tmp_path,
    )
    assert result["status"] == "BLOCKED_ROOT_DENY"
    assert result["evidence_digest"]


def test_expanded_recovery_root_action_is_denied(tmp_path: Path):
    result = run_task(
        {
            "role": "builder",
            "action": "authentication_or_recovery_factor_change",
            "command": ["python", "-c", "print('bad')"],
        },
        tmp_path,
    )
    assert result["status"] == "BLOCKED_ROOT_DENY"
    assert "authentication_or_recovery_factor_change" in result["denied"]


def test_judge_is_non_mutating_by_default():
    decision = authorize_task(
        {
            "role": "judge",
            "action": "write:repository_file",
        }
    )
    assert decision["status"] == "DENY_ROLE_MODE"


def test_consequential_mutation_requires_independent_judge():
    decision = authorize_task(
        {
            "role": "builder",
            "action": "write:repository_file",
            "consequential": True,
        }
    )
    assert decision["status"] == "REQUIRES_INDEPENDENT_JUDGE"
    assert decision["requires_judge"] is True


def test_judge_verified_consequential_mutation_can_execute(tmp_path: Path):
    result = run_task(
        {
            "role": "builder",
            "action": "write:repository_file",
            "consequential": True,
            "judge_verified": True,
            "command": ["python", "-c", "print('verified')"],
        },
        tmp_path,
    )
    assert result["status"] == "PASS"
    assert result["requires_judge"] is True
    assert "verified" in result["stdout"]


def test_release_role_is_recognized():
    decision = authorize_task(
        {
            "role": "release",
            "action": "execute:bounded_task",
        }
    )
    assert decision["status"] == "AUTHORIZED_BOUNDED"


def test_invalid_command(tmp_path: Path):
    result = run_task(
        {"role": "planner", "command": ["python", 7]},
        tmp_path,
    )
    assert result["status"] == "INVALID_TASK"
    assert result["reason"] == "invalid_command"
    assert result["evidence_digest"]


def test_timeout_records_evidence(tmp_path: Path, monkeypatch):
    def timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=args[0],
            timeout=kwargs["timeout"],
            output="partial output",
            stderr="timed out",
        )

    monkeypatch.setattr(subprocess, "run", timeout_run)
    result = run_task(
        {"role": "judge", "command": ["python", "-c", "pass"], "timeout": 1},
        tmp_path,
    )
    assert result["status"] == "TIMEOUT"
    assert result["timeout_s"] == 1
    assert result["evidence_digest"]
