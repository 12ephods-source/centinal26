from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_contract_is_fail_closed() -> None:
    data = json.loads(
        (ROOT / "physics/ftoe/protected_i_uv_matching_source_audit_v20.json").read_text(
            encoding="utf-8"
        )
    )
    assert data["verdict"] == "UNRESOLVED_UV_MATCHING_BIFURCATION"
    assert data["scientific_status"] == "REVIEW_FAIL_CLOSED"
    assert data["checks"]["existing_reference_closes_both_requirements"] is False
    assert "explicit versioned interaction/matching Lagrangian" in data["smallest_missing_input"]


def test_checker_reproduces_frozen_verdict() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ftoe_protected_i_uv_matching_source_audit_v20.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["execution_pass"] is True
    assert result["scientific_pass"] is False
    assert result["verdict"] == "UNRESOLVED_UV_MATCHING_BIFURCATION"
