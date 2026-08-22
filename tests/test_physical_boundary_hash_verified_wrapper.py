from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "deploy" / "termux" / "physical_boundary_solver" / "run_hash_verified.sh"


FAKE_SOLVER = r'''#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$FROST_BOUNDARY_HOME" "$EVIDENCE_ROOT"
status="${FAKE_STATUS:-PHYSICAL_CLEANER_PROOF_DELETE_VERIFIED_LOCALLY}"
printf '{\n  "status": "%s"\n}\n' "$status" > "$FROST_BOUNDARY_HOME/status.json"
if [ "${FAKE_RC:-0}" -ne 0 ]; then
  exit "$FAKE_RC"
fi
zip="$EVIDENCE_ROOT/FrostForgePhysicalBoundaryEvidence_20990101T000000Z.zip"
printf 'device-evidence-bytes\n' > "$zip"
sha256sum "$zip" > "$zip.sha256"
if [ "${FAKE_TAMPER:-0}" = "1" ]; then
  printf 'tamper\n' >> "$zip"
fi
'''


def run_case(**extra: str) -> tuple[int, dict[str, object]]:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        state = home / "state"
        evidence = home / "evidence"
        fake = home / "fake_solver.sh"
        fake.write_text(FAKE_SOLVER, encoding="utf-8")
        fake.chmod(0o755)
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "FROST_BOUNDARY_HOME": str(state),
                "EVIDENCE_ROOT": str(evidence),
                "FROST_SOLVER_BIN": str(fake),
            }
        )
        env.update(extra)
        result = subprocess.run(
            ["bash", str(WRAPPER)],
            text=True,
            capture_output=True,
            env=env,
            timeout=10,
            check=False,
        )
        status_path = state / "hash-verified" / "status.json"
        assert status_path.exists(), (result.stdout, result.stderr)
        return result.returncode, json.loads(status_path.read_text(encoding="utf-8"))


def test_wrapper_shell_syntax() -> None:
    result = subprocess.run(["bash", "-n", str(WRAPPER)], check=False)
    assert result.returncode == 0


def test_delete_proof_requires_and_verifies_device_hash() -> None:
    rc, state = run_case()
    assert rc == 0
    assert state["status"] == "REAL_DEVICE_EXECUTED_EVIDENCE_PRESERVED_HASH_VERIFIED"
    assert len(str(state["sha256"])) == 64


def test_no_delete_qualification_is_separate_terminal_state() -> None:
    rc, state = run_case(FAKE_STATUS="PHYSICAL_CLEANER_INSTALLED_QUALIFIED_NO_DELETE_NEEDED")
    assert rc == 0
    assert state["status"] == "REAL_DEVICE_QUALIFIED_NO_DELETE_EVIDENCE_PRESERVED_HASH_VERIFIED"


def test_hash_mismatch_fails_closed() -> None:
    rc, state = run_case(FAKE_TAMPER="1")
    assert rc == 33
    assert state["status"] == "EVIDENCE_HASH_MISMATCH"


def test_nonpromotable_solver_status_fails_closed() -> None:
    rc, state = run_case(FAKE_STATUS="DEVICE_ACTION_REQUIRED_ADB_OR_LIBRARY_UI")
    assert rc == 30
    assert state["status"] == "SOLVER_STATUS_NOT_PROMOTABLE"


def test_solver_failure_is_preserved_not_promoted() -> None:
    rc, state = run_case(FAKE_RC="22")
    assert rc == 22
    assert state["status"] == "SOLVER_NOT_TERMINAL"
