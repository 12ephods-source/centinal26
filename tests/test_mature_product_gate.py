from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "mature_product_gate.py"
SPEC = importlib.util.spec_from_file_location("mature_product_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def host_pass() -> dict[str, bool]:
    return {
        "functional_pass": True,
        "regression_pass": True,
        "rollback_verified": True,
    }


def device_pass() -> dict[str, object]:
    return {
        "platform": "android/termux",
        "fresh_heartbeat": True,
        "bounded_job_completed": True,
        "independent_verification": True,
        "forbidden_capability_rejected": True,
        "pre_boot_id": "boot-a",
        "post_boot_id": "boot-b",
        "post_reboot_heartbeat": True,
        "endurance_pass": True,
    }


def test_missing_device_is_blocked_external() -> None:
    result = MODULE.evaluate(host_pass())
    assert result["status"] == "BLOCKED_EXTERNAL"
    assert result["hard_gate_pass"] is False


def test_all_hard_gates_produce_mature() -> None:
    result = MODULE.evaluate(host_pass(), device_pass())
    assert result["status"] == "MATURE"
    assert result["hard_gate_pass"] is True


def test_unchanged_boot_id_blocks_maturity() -> None:
    device = device_pass()
    device["post_boot_id"] = device["pre_boot_id"]
    result = MODULE.evaluate(host_pass(), device)
    assert result["status"] == "NOT_MATURE"
    assert result["hard_gate_pass"] is False


def test_fitness_cannot_mask_failed_hard_gate() -> None:
    device = device_pass()
    device["independent_verification"] = False
    device["performance_score"] = 1.0
    result = MODULE.evaluate(host_pass(), device)
    assert result["status"] == "NOT_MATURE"
    assert result["hard_gate_pass"] is False
