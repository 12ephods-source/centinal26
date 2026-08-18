from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_base44_worker_reuses_centinal_device_identity():
    script = text("deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh")
    assert 'INSTANCE_FILE="$STATE_ROOT/device-identity.json"' in script
    assert '"schema":"centinal26-device-identity-v1"' in script
    assert 'platform:"android/termux"' in script
    assert 'instance_id: instanceId' in script


def test_base44_worker_is_probe_only_and_denies_remote_install_shell_and_workflow():
    script = text("deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh")
    assert 'const ALLOWED = new Set(["system.health", "system.capabilities"]);' in script
    assert '["deny-shell", !allowed("shell.exec")]' in script
    assert '["deny-workflow", !allowed("workflow.execute")]' in script
    assert '["deny-install", !allowed("capability.ensure")]' in script
    assert 'spawn(' not in script
    assert 'exec(' not in script


def test_credentials_are_local_and_not_embedded():
    script = text("deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh")
    assert 'chmod 600 "$CFG"' in script
    assert "BASE44_TOKEN" in script
    assert "BASE44_PASSWORD" in script
    assert "AUTH_REQUIRED" in script
    assert "exit 20" in script


def test_termux_boot_recovers_worker():
    script = text("deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh")
    assert 'start-frost-fleet-worker.sh' in script
    assert 'frost-fleet-worker-start' in script
    assert 'sleep 20' in script


def test_v13_chains_exact_bridge_and_fleet_sources():
    script = text("deploy/termux/FROST_FLEET_BOOTSTRAP_v1.3.sh")
    assert 'BRIDGE_COMMIT="81bdbfacdd19f9041b34dace15756d62f8a777c6"' in script
    assert 'FLEET_COMMIT="00e37d65db71616e7e964d2d9d7eb0ea33a6a058"' in script
    assert 'FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh' in script
    assert 'FROST_FLEET_BOOTSTRAP_v1.2.sh' in script
    assert 'conversations/jobs -> required capability -> any eligible phone' in script
