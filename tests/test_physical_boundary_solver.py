from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / "deploy" / "termux" / "physical_boundary_solver" / "run.sh"


def text() -> str:
    return SOLVER.read_text(encoding="utf-8")


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
