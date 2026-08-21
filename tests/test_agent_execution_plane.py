from pathlib import Path

from automation.agent_execution_plane import run_task


def test_pass(tmp_path: Path):
    result = run_task(
        {"role": "builder", "command": ["python", "-c", "print('ok')"]},
        tmp_path,
    )
    assert result["status"] == "PASS" and "ok" in result["stdout"]


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
