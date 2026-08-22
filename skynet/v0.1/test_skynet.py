import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "skynet_core.py"

with tempfile.TemporaryDirectory() as temp_dir:
    env = dict(os.environ)
    env["SKYNET_HOME"] = temp_dir
    subprocess.check_call(
        ["python3", str(CORE), "init"],
        env=env,
        stdout=subprocess.DEVNULL,
    )
    output = subprocess.check_output(
        ["python3", str(CORE), "submit", "health"],
        env=env,
        text=True,
    )
    assert json.loads(output)["job"]["type"] == "health"
    output = subprocess.check_output(
        ["python3", str(CORE), "work-once"],
        env=env,
        text=True,
    )
    assert json.loads(output)["state"] == "done"
    output = subprocess.check_output(
        ["python3", str(CORE), "verify-audit"],
        env=env,
        text=True,
    )
    assert json.loads(output)["ok"] is True

print("PASS")
