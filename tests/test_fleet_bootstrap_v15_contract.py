from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v15_verifies_exact_git_blob_before_execution():
    script = text("deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.sh")
    assert 'WORKER_BLOB="6d061c4d704841972eaa1790888cea4f60816637"' in script
    assert 'PROVIDER_BLOB="0df8e008b85392a7c4768866d9b3987b9a909cfd"' in script
    assert 'FLEET_BLOB="8333db986588250ee99b79ad25f22d6a5b135e29"' in script
    assert "verify_git_blob" in script
    assert "sha1sum" in script
    assert "Git blob identity mismatch" in script


def test_v15_fetches_to_file_before_bash():
    script = text("deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.sh")
    assert 'curl -fsSL "$REPO_RAW/$commit/$path" -o "$out"' in script
    assert 'verify_git_blob "$out" "$expected_blob"' in script
    assert 'bash -n "$out"' in script
    assert 'bash "$out"' in script
    assert "| bash" not in script


def test_v15_preserves_bounded_remote_authority():
    script = text("deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.sh")
    assert "system.health, system.capabilities, capability.ensure" in script
    assert "arbitrary remote shell: disabled" in script
    assert "arbitrary package names from jobs: disabled" in script
