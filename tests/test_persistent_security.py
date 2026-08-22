import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "persistent_security", ROOT / "automation/persistent/security.py"
)
security = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security)


def good_context():
    return {
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


policy = security.SecurityPolicy()
base = policy.evaluate(good_context())
assert base.allowed
assert not base.reasons

ctx = good_context()
ctx["authority_verified"] = False
assert "authority_verified" in policy.evaluate(ctx).reasons

ctx = good_context()
ctx["capabilities"].append("unrestricted_shell")
assert "no_forbidden_capability" in policy.evaluate(ctx).reasons

ctx = good_context()
ctx["baseline"] = {
    "source": "current_snapshot",
    "expected_sha256": "a" * 64,
    "actual_sha256": "a" * 64,
}
assert "trusted_provenance" in policy.evaluate(ctx).reasons

ctx = good_context()
ctx["device"]["origin_verified"] = False
assert "device_claim_valid" in policy.evaluate(ctx).reasons

ctx = good_context()
ctx["claim"] = {"status": "OBSERVED", "source": "model"}
assert "epistemic_claim_valid" in policy.evaluate(ctx).reasons

ctx = good_context()
ctx["destructive_action"] = True
assert "destructive_action_authorized" in policy.evaluate(ctx).reasons
ctx["destructive_authorized"] = True
assert policy.evaluate(ctx).allowed

print("persistent_security_tests=PASS")
