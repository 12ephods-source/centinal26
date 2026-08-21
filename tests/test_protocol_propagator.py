import json
import subprocess
import sys
from pathlib import Path


def test_protocol_propagator_installs_and_preserves_old_prompt(tmp_path: Path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    old = target / "PROMPT_BOOTSTRAP.md"
    old.write_text("legacy project prompt\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, "tools/protocol_propagator.py", str(target)],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    canonical = Path(__file__).resolve().parents[1] / "protocols" / "FROST_MASTER_PROJECT_PROTOCOL_v2.md"
    assert old.read_bytes() == canonical.read_bytes()
    backups = list(target.glob("PROMPT_BOOTSTRAP.pre-v2.*.md"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "legacy project prompt\n"

    record = json.loads((target / "PROTOCOL_INSTALLATION.json").read_text(encoding="utf-8"))
    assert record["protocol_id"] == "frost-master-project-protocol"
    assert record["version"] == "2.0"
    assert record["installation_status"] == "INSTALLED_VERIFIED"
    assert record["verification_status"] == "VERIFIED"
