import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "automation" / "runtime" / "executor_registry.json"
BINDING = (
    ROOT
    / "automation"
    / "runtime"
    / "executors"
    / "executor_registry_binding.json"
)


def test_executor_registry_reports_verified_host_state_without_overpromoting_android():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    statuses = {
        executor["executor_id"]: executor["verification_status"]
        for executor in registry["executors"]
    }

    assert registry["status"] == "HOST_INTEGRATION_VERIFIED_ANDROID_PENDING_PHYSICAL"
    assert statuses["local_python_executor"] == "HOST_INTEGRATION_VERIFIED"
    assert statuses["repository_executor"] == "HOST_INTEGRATION_VERIFIED"
    assert statuses["api_connector_executor"] == (
        "HOST_INTEGRATION_VERIFIED_TARGET_AUTHORIZATION_SEPARATE"
    )
    assert statuses["agent_execution_plane"] == "HOST_BEHAVIORAL_AND_INTEGRATION_VERIFIED"
    assert statuses["android_worker_executor"] == (
        "HOST_CONTRACT_VERIFIED_PHYSICAL_WORKER_PENDING"
    )
    assert "issue #208" in next(
        executor["physical_requirement"]
        for executor in registry["executors"]
        if executor["executor_id"] == "android_worker_executor"
    )


def test_legacy_binding_descriptor_points_to_canonical_registry():
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    assert binding["executors"] == []
    assert binding["canonical_registry"] == "automation/runtime/executor_registry.json"
    assert binding["status"] == "COMPATIBILITY_DESCRIPTOR_USE_CANONICAL_REGISTRY"
