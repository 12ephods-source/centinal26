from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from centinal26.hard_sandbox import (
    BubblewrapEvaluator,
    SandboxLimits,
    SandboxUnavailable,
    verify_result_hash,
)

COMMIT = "a" * 40
GOAL = "b" * 64
VALIDATORS = {"pytest": "9.1.1", "sandbox-contract": "1"}


def _live_evaluator() -> BubblewrapEvaluator:
    evaluator = BubblewrapEvaluator()
    required = os.environ.get("CENTINAL26_HARD_SANDBOX_REQUIRED") == "1"
    if shutil.which("bwrap") is None:
        if required:
            pytest.fail("bubblewrap is required by the hard-sandbox CI gate")
        pytest.skip("bubblewrap is not installed")
    try:
        evaluator.probe()
    except SandboxUnavailable as error:
        if required:
            pytest.fail(str(error))
        pytest.skip(str(error))
    return evaluator


def _write(root: Path, name: str, source: str) -> Path:
    path = root / name
    path.write_text(source, encoding="utf-8")
    return path


def _run(
    evaluator: BubblewrapEvaluator,
    root: Path,
    script: str,
    *,
    limits: SandboxLimits | None = None,
):
    return evaluator.evaluate(
        root,
        candidate_commit=COMMIT,
        goal_digest=GOAL,
        command=["/usr/bin/python3", f"/src/{script}"],
        validator_versions=VALIDATORS,
        limits=limits,
    )


def test_unavailable_sandbox_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    root.mkdir()
    _write(root, "ok.py", "print('should not execute')\n")
    evaluator = BubblewrapEvaluator(tmp_path / "does-not-exist")

    with pytest.raises(SandboxUnavailable, match="unavailable"):
        evaluator.evaluate(
            root,
            candidate_commit=COMMIT,
            goal_digest=GOAL,
            command=["/usr/bin/python3", "/src/ok.py"],
            validator_versions=VALIDATORS,
        )


def test_live_network_environment_mount_and_source_write_denial(tmp_path: Path) -> None:
    evaluator = _live_evaluator()
    root = tmp_path / "candidate"
    root.mkdir()
    secret = tmp_path / "host-secret.txt"
    secret.write_text("HOST_SECRET_314159", encoding="utf-8")
    (root / "outside-link").symlink_to(secret)
    _write(
        root,
        "isolation.py",
        """
import os
import socket

checks = {}
checks['env_secret_absent'] = os.environ.get('FROST_SANDBOX_TEST_SECRET') is None
try:
    open('/src/outside-link').read()
    checks['outside_mount_denied'] = False
except OSError:
    checks['outside_mount_denied'] = True
try:
    open('/src/mutation.txt', 'w').write('mutated')
    checks['source_read_only'] = False
except OSError:
    checks['source_read_only'] = True
sock = socket.socket()
sock.settimeout(0.5)
try:
    sock.connect(('1.1.1.1', 53))
    checks['network_denied'] = False
except OSError:
    checks['network_denied'] = True
finally:
    sock.close()
checks['home_empty'] = not os.path.exists('/home/runner')
print(__import__('json').dumps(checks, sort_keys=True))
""".lstrip(),
    )
    os.environ["FROST_SANDBOX_TEST_SECRET"] = "DO_NOT_INHERIT"
    try:
        result = _run(evaluator, root, "isolation.py")
    finally:
        os.environ.pop("FROST_SANDBOX_TEST_SECRET", None)

    assert result.exit_code == 0, result.stderr
    checks = json.loads(result.stdout)
    assert all(checks.values()), checks
    assert not (root / "mutation.txt").exists()
    assert verify_result_hash(result)
    assert result.isolation["host_execution_fallback"] is False


def test_wall_clock_limit_is_enforced(tmp_path: Path) -> None:
    evaluator = _live_evaluator()
    root = tmp_path / "candidate"
    root.mkdir()
    _write(root, "sleep.py", "import time\ntime.sleep(10)\n")

    result = _run(
        evaluator,
        root,
        "sleep.py",
        limits=SandboxLimits(wall_seconds=0.25),
    )

    assert result.timed_out is True
    assert result.duration_seconds < 3
    assert result.exit_code != 0
    assert verify_result_hash(result)


def test_output_limit_is_enforced(tmp_path: Path) -> None:
    evaluator = _live_evaluator()
    root = tmp_path / "candidate"
    root.mkdir()
    _write(root, "output.py", "import sys\nsys.stdout.write('X' * 1000000)\nsys.stdout.flush()\n")

    result = _run(
        evaluator,
        root,
        "output.py",
        limits=SandboxLimits(output_bytes=2048),
    )

    assert result.output_limited is True
    assert len(result.stdout.encode()) <= 2048
    assert result.exit_code != 0


def test_cpu_and_memory_limits_are_visible_and_enforced(tmp_path: Path) -> None:
    evaluator = _live_evaluator()
    memory_root = tmp_path / "memory"
    memory_root.mkdir()
    _write(
        memory_root,
        "memory.py",
        """
try:
    value = bytearray(512 * 1024 * 1024)
    print('MEMORY_NOT_DENIED', len(value))
except MemoryError:
    print('MEMORY_DENIED')
""".lstrip(),
    )
    memory_result = _run(
        evaluator,
        memory_root,
        "memory.py",
        limits=SandboxLimits(memory_bytes=128 * 1024 * 1024),
    )
    assert "MEMORY_DENIED" in memory_result.stdout or memory_result.exit_code != 0

    cpu_root = tmp_path / "cpu"
    cpu_root.mkdir()
    _write(cpu_root, "cpu.py", "while True:\n    pass\n")
    cpu_result = _run(
        evaluator,
        cpu_root,
        "cpu.py",
        limits=SandboxLimits(cpu_seconds=1, wall_seconds=4),
    )
    assert cpu_result.exit_code != 0
    assert cpu_result.timed_out is False
    assert cpu_result.duration_seconds < 4


def test_process_limit_prevents_unbounded_forking(tmp_path: Path) -> None:
    evaluator = _live_evaluator()
    root = tmp_path / "candidate"
    root.mkdir()
    _write(
        root,
        "fork.py",
        """
import os
import time

children = []
denied = False
try:
    for _ in range(128):
        try:
            pid = os.fork()
        except OSError:
            denied = True
            break
        if pid == 0:
            time.sleep(2)
            os._exit(0)
        children.append(pid)
finally:
    for pid in children:
        try:
            os.kill(pid, 9)
        except OSError:
            pass
    for pid in children:
        try:
            os.waitpid(pid, 0)
        except OSError:
            pass
print('PROCESS_DENIED' if denied else 'PROCESS_NOT_DENIED')
""".lstrip(),
    )

    result = _run(
        evaluator,
        root,
        "fork.py",
        limits=SandboxLimits(processes=16, wall_seconds=5),
    )

    assert "PROCESS_DENIED" in result.stdout, result.stdout + result.stderr


def test_result_hash_binds_candidate_goal_validators_and_evidence(tmp_path: Path) -> None:
    evaluator = _live_evaluator()
    root = tmp_path / "candidate"
    root.mkdir()
    _write(root, "ok.py", "print('ok')\n")

    result = _run(evaluator, root, "ok.py")
    assert result.exit_code == 0
    assert verify_result_hash(result)

    tampered = result.as_dict()
    tampered["candidate_commit"] = "c" * 40
    assert not verify_result_hash(tampered)
    tampered = result.as_dict()
    tampered["goal_digest"] = "d" * 64
    assert not verify_result_hash(tampered)
