import hashlib
import json
import os
import subprocess
import sys
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
    for profile in (
        "centinal26-core",
        "android-fleet",
        "hermes-c05",
        "device-validation",
    ):
        assert profile in value["profiles"]
        assert value["profiles"][profile]


def test_dependency_is_explicit():
    value = registry()
    assert value["modules"]["capability-provider-v1.0"]["depends_on"] == [
        "base44-worker-v1.0"
    ]
    assert value["modules"]["device-validation-adapter-v1.0"]["depends_on"] == [
        "capability-provider-v1.0"
    ]


def test_device_validation_profile_is_bounded():
    value = registry()
    spec = value["modules"]["device-validation-adapter-v1.0"]
    assert spec["source"]["path"] == (
        "deploy/termux/FROST_DEVICE_VALIDATION_ADAPTER_v1.0.sh"
    )
    assert spec["source"]["git_blob_sha1"] == (
        "0b5d7b00ce4d8dd0af0ca7a73dcc40124c1dc647"
    )
    assert value["profiles"]["device-validation"] == [
        "device-validation-adapter-v1.0"
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


def test_verify_rejects_staged_module(tmp_path):
    module_manager = ROOT / "deploy/automation_os/module_manager.py"
    value = registry()
    module_name = "centinal26-core-v1.0"
    fake = tmp_path / "fake.sh"
    fake.write_bytes(b"#!/usr/bin/env bash\ntrue\n")
    data = fake.read_bytes()
    blob = hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data,
        usedforsecurity=False,
    ).hexdigest()

    value["modules"][module_name]["source"]["git_blob_sha1"] = blob
    regdir = tmp_path / "registry"
    statedir = tmp_path / "state"
    regdir.mkdir()
    statedir.mkdir()
    (regdir / "registry.json").write_text(json.dumps(value), encoding="utf-8")
    state = {
        "schema_version": 1,
        "modules": {
            module_name: {
                "status": "STAGED",
                "artifact": str(fake),
                "source": value["modules"][module_name]["source"],
            }
        },
        "history": [],
    }
    (statedir / "module_state.json").write_text(json.dumps(state), encoding="utf-8")

    env = os.environ.copy()
    env["AUTOMATION_OS_ROOT"] = str(tmp_path)
    env["AUTOMATION_OS_TEST_MODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(module_manager), "verify"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    report = json.loads(result.stdout)
    assert result.returncode == 2
    assert report["ok"] is False
    item = report["modules"][module_name]
    assert item["source_identity_ok"] is True
    assert item["installation_state_ok"] is False
