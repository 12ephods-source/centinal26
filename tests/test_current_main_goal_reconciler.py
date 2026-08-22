import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "automation/persistent/current_main_goal_reconciler.py"
spec = importlib.util.spec_from_file_location("current_main_goal_reconciler", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _git(path, *args):
    subprocess.check_call(["git", "-C", str(path), *args])


def _repo():
    td = tempfile.TemporaryDirectory()
    root = pathlib.Path(td.name)
    bare = root / "remote.git"
    work = root / "work"
    _git(root, "init", "--bare", str(bare))
    _git(root, "clone", str(bare), str(work))
    _git(work, "config", "user.email", "test@example.invalid")
    _git(work, "config", "user.name", "test")
    (work / "x").write_text("1\n")
    _git(work, "add", "x")
    _git(work, "commit", "-m", "initial")
    _git(work, "branch", "-M", "main")
    _git(work, "push", "-u", "origin", "main")
    _git(work, "fetch", "origin", "main")
    return td, work


def _checks():
    keys = (
        "repo_sync", "repo_clean", "pair_ok", "skynet_ok", "state_integrity_ok",
        "recovery_ok", "security_policy_ok", "device_boot_ok", "device_restart_ok",
        "device_exec_ok", "device_audit_ok",
    )
    return {k: True for k in keys}


def test_current_release_can_complete():
    td, repo = _repo()
    try:
        release = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "origin/main"], text=True).strip()
        state = pathlib.Path(td.name) / "state.json"
        state.write_text(json.dumps({"release": release, "checks": _checks()}))
        result = mod.reconcile(repo, state)
        assert result["stale_release"] is False
        assert result["software_release_complete"] is True
        assert result["deployed_app_complete"] is True
    finally:
        td.cleanup()


def test_stale_release_is_demoted_even_with_true_checks():
    td, repo = _repo()
    try:
        state = pathlib.Path(td.name) / "state.json"
        state.write_text(json.dumps({"release": "0" * 40, "checks": _checks()}))
        result = mod.reconcile(repo, state)
        assert result["stale_release"] is True
        assert result["software_release_complete"] is False
        assert result["deployed_app_complete"] is False
    finally:
        td.cleanup()
