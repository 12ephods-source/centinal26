import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SCENARIOS = [
    "stale_alias_writer",
    "wrong_restore_hash",
    "live_wal_restore",
    "corrupt_snapshot",
    "interrupted_restore_temp",
    "manifest_symlink",
    "encrypted_backup_provider_missing",
]


def run_chaos(output: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, "scripts/run_host_chaos_qualification.py", "--output", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.stdout.strip() == "PASS"
    return json.loads(output.read_text(encoding="utf-8"))


def test_host_chaos_campaign_passes_every_registered_scenario(tmp_path) -> None:
    report = run_chaos(tmp_path / "chaos.json")
    assert report["status"] == "PASS"
    assert report["scope"] == "HOST_ONLY"
    assert report["physical_promotion_allowed"] is False
    assert [item["scenario"] for item in report["scenarios"]] == EXPECTED_SCENARIOS
    assert all(item["status"] == "PASS" for item in report["scenarios"])
    assert len(report["report_sha256"]) == 64


def test_host_chaos_report_is_deterministic(tmp_path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    one = run_chaos(first)
    two = run_chaos(second)
    assert one == two
    assert first.read_bytes() == second.read_bytes()
