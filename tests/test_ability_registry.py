import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ability_registry.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_canonical_registry_validates() -> None:
    result = run_cli("validate")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ABILITY_REGISTRY_VALID" in result.stdout


def test_register_requires_verification_and_provenance(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"schema_version": "1.0", "policy": {}, "abilities": []}),
        encoding="utf-8",
    )
    ability = tmp_path / "ability.json"
    ability.write_text(
        json.dumps(
            {
                "id": "test/missing-evidence/v1",
                "name": "Missing evidence",
                "kind": "tool",
                "source": {},
                "interface": {},
                "status": "VERIFIED",
            }
        ),
        encoding="utf-8",
    )
    result = run_cli("--registry", str(registry), "register", str(ability))
    assert result.returncode == 2
    assert "verification" in result.stdout
    assert "provenance" in result.stdout


def test_register_rejects_duplicate_id(tmp_path: Path) -> None:
    ability = {
        "id": "test/reusable/v1",
        "name": "Reusable test ability",
        "kind": "verifier",
        "source": {"path": "scripts/example.py"},
        "interface": {"command": "python scripts/example.py"},
        "verification": {"status": "PASS"},
        "provenance": {"origin": "test"},
        "status": "VERIFIED",
    }
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"schema_version": "1.0", "policy": {}, "abilities": [ability]}),
        encoding="utf-8",
    )
    ability_path = tmp_path / "ability.json"
    ability_path.write_text(json.dumps(ability), encoding="utf-8")
    result = run_cli("--registry", str(registry), "register", str(ability_path))
    assert result.returncode == 2
    assert "already exists" in result.stdout


def test_registry_policy_never_grants_authority() -> None:
    data = json.loads((ROOT / "automation" / "abilities" / "registry.json").read_text())
    assert data["policy"]["missing_capability"] == "BUILD_TEST_REGISTER_REUSE_WHEN_AUTHORIZED"
    assert data["policy"]["external_boundary"] == "RECORD_BLOCKER_AND_CONTINUE"
    assert "no_authority_expansion" in data["policy"]["requirements"]
