import importlib.util
import json
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "pk", ROOT / "automation/persistent/kernel.py"
)
pk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pk)

ALL = {key: True for key in pk.QUALIFIED}
SECURITY = {
    "authority_verified": True,
    "capability_authorized": True,
    "bounded_execution": True,
    "independent_verification": True,
    "evidence_chain_valid": True,
    "capabilities": ["repo_sync", "state_update"],
    "baseline": {
        "source": "trusted_git",
        "expected_sha256": "a" * 64,
        "actual_sha256": "a" * 64,
    },
    "device": {
        "claimed": True,
        "origin": "ANDROID_TERMUX",
        "origin_verified": True,
        "report_sha256": "b" * 64,
    },
    "claim": {"status": "VERIFIED", "source": "deterministic_verifier"},
    "secret_exposure": False,
    "destructive_action": False,
}

with tempfile.TemporaryDirectory() as td:
    kernel = pk.Kernel(pathlib.Path(td))
    first = kernel.commit(
        "r1", ALL, "initial", "test", {"fixture": "all-pass"}, SECURITY
    )
    assert first["goal_reached"]
    assert first["status"] == "PROJECT_GOAL_REACHED"
    assert first["security"]["allowed"]
    assert kernel.marker.exists()
    assert kernel.verify() == []

    broken = dict(ALL)
    broken["device_restart_ok"] = False
    demoted = kernel.commit("r1", broken, "fault:restart", "test", {}, SECURITY)
    assert not demoted["goal_reached"]
    assert demoted["status"] == "DEMOTED"
    assert not kernel.marker.exists()
    assert demoted["metrics"]["demotions"] == 1
    assert kernel.verify() == []

    recovered = kernel.commit("r1", ALL, "recovered:restart", "test", {}, SECURITY)
    assert recovered["goal_reached"]
    assert recovered["metrics"]["recoveries"] == 1
    assert kernel.verify() == []

    unsafe = dict(SECURITY)
    unsafe["authority_verified"] = False
    blocked = kernel.commit("r1", ALL, "fault:authority", "test", {}, unsafe)
    assert not blocked["goal_reached"]
    assert not blocked["checks"]["security_policy_ok"]
    assert "authority_verified" in blocked["security"]["reasons"]
    assert kernel.verify() == []

    # Corruption must be detected, never silently promoted.
    state = kernel.state
    obj = json.loads(state.read_text())
    obj["checks"]["repo_sync"] = False
    state.write_text(json.dumps(obj) + "\n")
    assert "state_hash" in kernel.verify()

print("persistent_kernel_tests=PASS")
