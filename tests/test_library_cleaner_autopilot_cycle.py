from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "deploy" / "termux" / "library_cleaner" / "autopilot_cycle.py"


def load_module():
    spec = importlib.util.spec_from_file_location("library_cleaner_autopilot", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_static_scan_detects_high_risk_patterns(tmp_path: Path) -> None:
    module = load_module()
    bad = tmp_path / "bad.sh"
    bad.write_text("#!/bin/sh\nrm -rf /\n", encoding="utf-8")
    findings = module.scan_path(bad)
    assert any(item["rule"] == "destructive_root_delete" for item in findings)


def test_static_scan_accepts_bounded_subprocess_usage(tmp_path: Path) -> None:
    module = load_module()
    good = tmp_path / "good.py"
    good.write_text(
        "import subprocess\nsubprocess.run(['adb', 'get-state'], check=False)\n",
        encoding="utf-8",
    )
    assert module.scan_path(good) == []


def test_disarm_forces_auto_delete_false(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module, "APP", tmp_path)
    monkeypatch.setattr(module, "CFG", tmp_path / "config.json")
    monkeypatch.setattr(module, "LOG", tmp_path / "autopilot-cycle.jsonl")
    monkeypatch.setattr(module, "RESULT", tmp_path / "qualification-result.json")
    monkeypatch.setattr(module, "SERVICE", tmp_path / "missing-service")
    module.CFG.write_text(json.dumps({"auto_delete": True}), encoding="utf-8")

    action = module.disarm("TEST")

    config = json.loads(module.CFG.read_text(encoding="utf-8"))
    assert action == {"action": "DISARM", "reason": "TEST"}
    assert config["auto_delete"] is False
    assert config["autopilot_disarm_reason"] == "TEST"


def test_qualification_receipt_requires_zero_errors(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    result_path = tmp_path / "qualification-result.json"
    monkeypatch.setattr(module, "RESULT", result_path)

    result_path.write_text(json.dumps({"errors": ["ADB_NOT_CONNECTED"]}), encoding="utf-8")
    assert module.qualification_clean() is False

    result_path.write_text(json.dumps({"errors": []}), encoding="utf-8")
    assert module.qualification_clean() is True


def test_autopilot_never_introduces_new_delete_authority() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "explicit_delete_names" not in text
    assert "safe_delete_patterns" not in text
    assert "undocumented_private_provider_endpoint" in text
    assert "visible_authenticated_ui_with_archive_before_delete" in text
