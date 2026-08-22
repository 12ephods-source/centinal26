from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "deploy" / "termux" / "physical_boundary_solver" / "termux_entrypoint.sh"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", str(ENTRY), *args],
        cwd=ROOT,
        env=run_env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def test_entrypoint_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(ENTRY)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_host_classification_is_not_termux() -> None:
    result = _run("--classify", env={"PREFIX": "/data/data/com.termux/files/usr"})
    assert result.returncode == 0
    assert result.stdout.strip() in {
        "HOST_OR_SESSION",
        "ANDROID_NON_TERMUX_OR_UNVERIFIED",
    }
    assert not result.stdout.startswith("ANDROID_TERMUX:")


def test_exported_prefix_alone_cannot_bypass_gate() -> None:
    result = _run("--self-test", env={"PREFIX": "/data/data/com.termux/files/usr"})
    assert result.returncode == 20
    assert "FROST_PHYSICAL_RUNTIME_ERROR" in result.stderr
    assert "host/session" in result.stderr or "not verified as Termux" in result.stderr


def test_entrypoint_does_not_claim_device_validation() -> None:
    text = ENTRY.read_text(encoding="utf-8")
    assert "DEVICE_VALIDATED" not in text
    assert "PERSISTENT_VALIDATED" not in text
    assert "exec \"$PREFIX/bin/bash\" \"$SOLVER\"" in text
