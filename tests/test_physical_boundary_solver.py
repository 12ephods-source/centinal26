import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / "deploy" / "termux" / "physical_boundary_solver" / "run.sh"


def text() -> str:
    return SOLVER.read_text(encoding="utf-8")


def run_host_solver(tmp_path: Path, action: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PREFIX"] = "/nontermux"
    env["FROST_BOUNDARY_HOME"] = str(tmp_path / "state")
    return subprocess.run(
        ["bash", str(SOLVER), action],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_physical_boundary_solver_is_fail_closed() -> None:
    body = text()
    assert "DEVICE_ACTION_REQUIRED_REAL_TERMUX" in body
    assert "DEVICE_ACTION_REQUIRED_ADB_OR_LIBRARY_UI" in body
    assert "max_deletes_per_cycle" in body and "=1" in body
    assert '"$APP/disarm.sh"' in body
    assert "adb mdns services" in body
    assert "FrostForgePhysicalBoundaryEvidence_" in body


def test_physical_boundary_solver_has_no_arbitrary_remote_shell() -> None:
    body = text()
    assert " ssh " not in body
    assert " nc " not in body
    assert "socat" not in body


def test_physical_boundary_solver_reuses_canonical_cleaner() -> None:
    body = text()
    assert 'CLEANER_DIR="$ROOT/deploy/termux/library_cleaner"' in body
    assert 'bash "$CLEANER_DIR/install.sh"' in body


def test_physical_boundary_solver_proof_stays_bounded_and_disarmed() -> None:
    body = text()
    assert 'd["max_deletes_per_cycle"]=1' in body
    assert '"$APP/disarm.sh"' in body
    assert 'sv down "$SERVICE"' in body
    assert 'sv up "$SERVICE"' not in body
    assert body.index('"$APP/disarm.sh"') < body.index('package_evidence "$run"')
    assert "first proof ends disarmed pending review" in body


def test_physical_boundary_solver_self_test_on_host_is_explicit(tmp_path: Path) -> None:
    result = run_host_solver(tmp_path, "--self-test")
    assert result.returncode == 0, result.stderr
    assert "SELF_TEST_PASS_HOST_DEVICE_ACTION_REQUIRED" in result.stdout
    assert "SELF_TEST_PASS_TERMUX" not in result.stdout


def test_physical_boundary_solver_run_on_host_cannot_claim_device_execution(
    tmp_path: Path,
) -> None:
    result = run_host_solver(tmp_path, "--run")
    assert result.returncode == 20, result.stderr
    assert "DEVICE_ACTION_REQUIRED_REAL_TERMUX" in result.stdout
    assert "PHYSICAL_CLEANER_PROOF_DELETE_VERIFIED_LOCALLY" not in result.stdout
    assert "PHYSICAL_CLEANER_INSTALLED_QUALIFIED_NO_DELETE_NEEDED" not in result.stdout
