from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_provider_registry_is_hardcoded_and_fail_closed():
    script = text("deploy/termux/FROST_CAPABILITY_PROVIDER_v1.0.sh")
    for mapping in (
        'python.runtime) package="python"',
        'git.client) package="git"',
        'node.runtime) package="nodejs-lts"',
        'json.jq) package="jq"',
        'hash.sha256) package="coreutils"',
        'process.procps) package="procps"',
        'crypto.openssl) package="openssl"',
        'network.curl) package="curl"',
        'termux.api.cli) package="termux-api"',
    ):
        assert mapping in script
    assert 'reason":"not_in_registry"' in script
    assert 'pkg install -y "$package"' in script
    assert "eval " not in script
    assert 'bash -c "$' not in script


def test_worker_allows_only_bounded_provider_not_shell_or_workflow():
    script = text("deploy/termux/FROST_CAPABILITY_PROVIDER_v1.0.sh")
    assert 'const ALLOWED = new Set(["system.health", "system.capabilities", "capability.ensure"]);' in script
    assert '["deny-shell", !allowed("shell.exec")]' in script
    assert '["deny-workflow", !allowed("workflow.execute")]' in script
    assert 'spawn(PROVIDER, args, {shell:false' in script
    assert '^[a-z0-9._-]{1,64}$' in script


def test_provider_subprocess_does_not_receive_base44_secrets():
    script = text("deploy/termux/FROST_CAPABILITY_PROVIDER_v1.0.sh")
    start = script.index("function providerEnv()")
    end = script.index("function runProvider", start)
    provider_env = script[start:end]
    assert "BASE44_TOKEN" not in provider_env
    assert "BASE44_PASSWORD" not in provider_env
    assert '["PATH","HOME","PREFIX","TMPDIR","LANG","LD_LIBRARY_PATH"]' in provider_env


def test_capability_ensure_requires_structured_registry_name():
    script = text("deploy/termux/FROST_CAPABILITY_PROVIDER_v1.0.sh")
    assert "capability.ensure requires parameters_json or payload_json containing a registry capability" in script
    assert "requestedCapability(job)" in script
    assert "provider.exit_code!==0" in script
    assert 'status:"failed"' in script


def test_v14_uses_immutable_worker_provider_and_physical_sources():
    script = text("deploy/termux/FROST_FLEET_BOOTSTRAP_v1.4.sh")
    assert 'WORKER_COMMIT="8db2f126b4f681e36f55eb668227cbb9c8747616"' in script
    assert 'PROVIDER_COMMIT="29a01b9a7432cc7a120c079d925eb3f86957d3b5"' in script
    assert 'FLEET_COMMIT="00e37d65db71616e7e964d2d9d7eb0ea33a6a058"' in script
    assert "FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh" in script
    assert "FROST_CAPABILITY_PROVIDER_v1.0.sh" in script
    assert "FROST_FLEET_BOOTSTRAP_v1.2.sh" in script
    assert "arbitrary remote shell: disabled" in script
    assert "arbitrary package names from jobs: disabled" in script
