import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def registry():
    return json.loads((ROOT / "deploy/automation_os/registry.json").read_text())


def test_registry_is_fail_closed_and_pinned():
    value = registry()
    assert value["integrity_policy"]["fail_closed"] is True
    for spec in value["modules"].values():
        assert len(spec["source"]["commit"]) == 40
        assert len(spec["source"]["git_blob_sha1"]) == 40


def test_core_profiles_are_registered():
    value = registry()
    for profile in ("centinal26-core", "android-fleet", "hermes-c05"):
        assert profile in value["profiles"]
        assert value["profiles"][profile]


def test_dependency_is_explicit():
    value = registry()
    assert value["modules"]["capability-provider-v1.0"]["depends_on"] == [
        "base44-worker-v1.0"
    ]


def test_noncanonical_artifacts_fail_closed():
    value = registry()
    assert "AICCEP-OS" in value["known_artifacts_not_remotely_installable"]
    assert "AICCEP-OS" not in value["modules"]
    assert "GuardianLLM" not in value["modules"]


def test_v31_installer_pins_framework_bytes():
    text = (
        ROOT / "deploy/termux/AUTOMATION_OS_UNIVERSAL_INSTALLER_v3.1.sh"
    ).read_text()
    manager = hashlib.sha256(
        (ROOT / "deploy/automation_os/module_manager.py").read_bytes()
    ).hexdigest()
    registry_hash = hashlib.sha256(
        (ROOT / "deploy/automation_os/registry.json").read_bytes()
    ).hexdigest()
    assert manager in text
    assert registry_hash in text


def test_v30_bootstrap_is_frozen_to_its_qualified_head():
    text = (
        ROOT / "deploy/termux/AUTOMATION_OS_UNIVERSAL_INSTALLER_v3.0.sh"
    ).read_text()
    assert "2bbd048f57b7b4edb3b3b2935248316dd086c649" in text
