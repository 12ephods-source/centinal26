import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_registry_is_fail_closed_and_pinned():
    r = json.loads((ROOT/"deploy/automation_os/registry.json").read_text())
    assert r["integrity_policy"]["fail_closed"] is True
    m = r["modules"]["frost-fleet-v1.7"]
    assert len(m["source"]["commit"]) == 40
    assert len(m["source"]["git_blob_sha1"]) == 40

def test_installer_pins_framework_bytes():
    text = (ROOT/"deploy/termux/AUTOMATION_OS_UNIVERSAL_INSTALLER_v3.0.sh").read_text()
    mgr = hashlib.sha256((ROOT/"deploy/automation_os/module_manager.py").read_bytes()).hexdigest()
    reg = hashlib.sha256((ROOT/"deploy/automation_os/registry.json").read_bytes()).hexdigest()
    assert mgr in text
    assert reg in text
