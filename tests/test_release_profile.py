import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "release_profile", ROOT / "automation/persistent/release_profile.py"
)
rp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rp
spec.loader.exec_module(rp)

software_only = {key: True for key in rp.SOFTWARE_REQUIRED}
profile = rp.evaluate(software_only)
assert profile.software_release_complete
assert not profile.deployed_app_complete
assert set(profile.deployment_missing) == {
    "device_boot_ok",
    "device_restart_ok",
    "device_exec_ok",
    "device_audit_ok",
}

all_pass = {key: True for key in rp.DEPLOYMENT_REQUIRED}
profile = rp.evaluate(all_pass)
assert profile.software_release_complete
assert profile.deployed_app_complete

broken_security = dict(all_pass)
broken_security["security_policy_ok"] = False
profile = rp.evaluate(broken_security)
assert not profile.software_release_complete
assert not profile.deployed_app_complete

fake_device_only = {
    "device_boot_ok": True,
    "device_restart_ok": True,
    "device_exec_ok": True,
    "device_audit_ok": True,
}
profile = rp.evaluate(fake_device_only)
assert not profile.software_release_complete
assert not profile.deployed_app_complete

print("release_profile_tests=PASS")
