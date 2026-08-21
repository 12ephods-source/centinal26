from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "termux" / "FROST_EVIDENCE_GATE_ONE_PASTE_v1.0.sh"


def test_one_paste_installer_has_valid_bash_syntax() -> None:
    completed = subprocess.run(
        ["bash", "-n", str(INSTALLER)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
