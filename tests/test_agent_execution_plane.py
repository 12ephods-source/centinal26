import subprocess
from pathlib import Path

from centinal26.agent_execution_plane import run_task


def test_pass(tmp_path: Path):
    result = run_task(
        {"role": "builder", "command": ["python", "-c", "print('ok')"]},
        tmp_path,
    )
    assert result["status"] == "PASS" and "ok" in result["stdout"]
    assert result["evidence_digest"]


def test_root_deny(tmp_path: Path):
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
