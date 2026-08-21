import json
from pathlib import Path
from automation.agent_execution_plane import run_task

def test_pass(tmp_path: Path):
    r=run_task({"role":"builder","command":["python","-c","print('ok')"]},tmp_path)
    assert r["status"]=="PASS" and "ok" in r["stdout"]

def test_root_deny(tmp_path: Path):
    r=run_task({"role":"sre","capabilities":["credential_root"],"command":["python","-c","print('bad')"]},tmp_path)
    assert r["status"]=="BLOCKED_ROOT_DENY"
