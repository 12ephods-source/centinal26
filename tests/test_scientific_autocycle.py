from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "automation" / "device" / "scientific_autocycle.py"
spec = importlib.util.spec_from_file_location("scientific_autocycle", MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_meta_requires_goal_and_success():
    raw = '# FROST-AUTORUN:2\n# FROST-CYCLE: {"goal":"prove x","success":{"exit_code":0}}\nprint(1)\n'
    meta = mod.load_cycle_meta(raw)
    assert meta["goal"] == "prove x"
    assert meta["success"]["exit_code"] == 0


def test_guardian_rejects_dangerous_shell(tmp_path: Path):
    path = tmp_path / "bad.sh"
    path.write_text("rm -rf /tmp/x\n", encoding="utf-8")
    report = mod.inspect_candidate(path, "bash")
    assert report.verdict == "REJECT"
    assert any(finding.detail == "recursive_force_delete" for finding in report.findings)


def test_guardian_flags_vibeware_for_review(tmp_path: Path):
    path = tmp_path / "stub.py"
    path.write_text("# TODO\nraise NotImplementedError\n", encoding="utf-8")
    report = mod.inspect_candidate(path, "python")
    assert report.verdict == "REVIEW"


def test_goal_predicate():
    meta = mod.validate_meta(
        {
            "goal": "g",
            "success": {
                "exit_code": 0,
                "required_text": ["PASS"],
                "forbidden_text": ["FAIL"],
            },
        }
    )
    ok, checks = mod.goal_satisfied(meta, 0, "PASS\n")
    assert ok
    assert all(check["pass"] for check in checks)


def test_perspective_adjudication_changes_by_situation():
    meta = mod.validate_meta(
        {
            "goal": "g",
            "success": {"exit_code": 0},
            "perspectives": list(mod.DEFAULT_PERSPECTIVES),
        }
    )
    success = {
        "goal_satisfied": True,
        "exit_code": 0,
        "duration_seconds": 0.1,
        "output": "ok",
    }
    failure = {
        "goal_satisfied": False,
        "exit_code": 2,
        "duration_seconds": 0.1,
        "output": "err",
    }
    assert mod.adjudicate_perspectives(meta, success)["situation"] == "nominal_success"
    assert mod.adjudicate_perspectives(meta, failure)["situation"] == "execution_failure"


def test_cycle_verifies_simple_goal(tmp_path: Path):
    candidate = tmp_path / "candidate.py"
    candidate.write_text("print('MEASURED_PASS')\n", encoding="utf-8")
    meta = mod.validate_meta(
        {
            "goal": "emit measured pass",
            "success": {"exit_code": 0, "required_text": ["MEASURED_PASS"]},
            "limits": {"max_iterations": 3, "episode_timeout_seconds": 5},
            "agent_providers": ["deterministic"],
        }
    )
    report = mod.run_cycle(candidate, meta, tmp_path / "state")
    assert report["status"] == "GOAL_VERIFIED"
    assert (Path(report["cycle_root"]) / "report.json").is_file()
    assert (Path(report["cycle_root"]) / "cycle.sqlite3").is_file()


def test_cycle_stops_when_no_revision_provider(tmp_path: Path):
    candidate = tmp_path / "candidate.py"
    candidate.write_text("print('NOPE')\n", encoding="utf-8")
    meta = mod.validate_meta(
        {
            "goal": "emit target",
            "success": {"exit_code": 0, "required_text": ["TARGET"]},
            "limits": {"max_iterations": 3, "episode_timeout_seconds": 5},
            "agent_providers": ["deterministic"],
        }
    )
    report = mod.run_cycle(candidate, meta, tmp_path / "state")
    assert report["status"] == "NO_IMPROVING_REVISION"


def test_event_chain_is_hash_linked(tmp_path: Path):
    store = mod.CycleStore(tmp_path / "events.sqlite3")
    try:
        first_hash = store.append("one", {"x": 1})
        second_hash = store.append("two", {"x": 2})
        rows = store.conn.execute(
            "SELECT prev_hash, event_hash FROM events ORDER BY seq"
        ).fetchall()
    finally:
        store.close()
    assert rows[0][0] == "0" * 64
    assert rows[0][1] == first_hash
    assert rows[1][0] == first_hash
    assert rows[1][1] == second_hash


def test_unregistered_agent_is_unavailable(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(
        "FROST_AUTOCYCLE_AGENT_REGISTRY", str(tmp_path / "missing.json")
    )
    candidate = tmp_path / "x.py"
    candidate.write_text("print(1)\n", encoding="utf-8")
    result = mod.run_external_agent("not-there", "prompt", candidate, 1)
    assert result["status"] == "UNAVAILABLE"


def test_stage_and_run_clipboard_v2(tmp_path: Path):
    raw = (
        "# FROST-AUTORUN:2 shell=python\n"
        '# FROST-CYCLE: {"goal":"emit pass","success":{"exit_code":0,'
        '"required_text":["CYCLE_PASS"]},"agent_providers":["deterministic"]}\n'
        "print('CYCLE_PASS')\n"
    )
    pending = mod.stage_clipboard(raw, tmp_path / "root")
    assert pending["status"] == "STAGED"
    report = mod.run_pending_clipboard(tmp_path / "root")
    assert report["status"] == "GOAL_VERIFIED"


def test_stage_rejects_unmarked_clipboard(tmp_path: Path):
    raw = '# FROST-CYCLE: {"goal":"x","success":{"exit_code":0}}\nprint(1)\n'
    try:
        mod.stage_clipboard(raw, tmp_path / "root")
    except ValueError as exc:
        assert "not marked" in str(exc)
    else:
        raise AssertionError("unmarked clipboard should be rejected")
