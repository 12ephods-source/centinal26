import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ability_registry.py"
POLICY = {
    "missing_capability": "BUILD_TEST_REGISTER_REUSE_WHEN_AUTHORIZED",
    "external_boundary": "RECORD_BLOCKER_AND_CONTINUE",
    "requirements": [
        "bounded_scope",
        "source_preserved",
        "tests_or_verification_preserved",
        "provenance_preserved",
        "interface_documented",
        "rollback_or_removal_path",
        "no_authority_expansion",
    ],
}


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def registry_document(abilities: list[dict] | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "policy": POLICY,
        "abilities": list(abilities or []),
    }


def valid_ability(ability_id: str = "test/reusable/v1") -> dict:
    return {
        "id": ability_id,
        "name": "Reusable test ability",
        "kind": "verifier",
        "source": {"path": "scripts/example.py"},
        "interface": {"command": "python scripts/example.py"},
        "verification": {"status": "PASS"},
        "provenance": {"origin": "test"},
        "lifecycle": {"removal": "delete the versioned registry entry in a successor"},
        "status": "VERIFIED",
    }


def test_canonical_registry_validates() -> None:
    result = run_cli("validate")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ABILITY_REGISTRY_VALID" in result.stdout


def test_register_requires_verification_provenance_and_lifecycle(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps(registry_document()), encoding="utf-8")
    ability = tmp_path / "ability.json"
    ability.write_text(
        json.dumps(
            {
                "id": "test/missing-evidence/v1",
                "name": "Missing evidence",
                "kind": "tool",
                "source": {"path": "scripts/example.py"},
                "interface": {"command": "python scripts/example.py"},
                "status": "VERIFIED",
            }
        ),
        encoding="utf-8",
    )
    result = run_cli("--registry", str(registry), "register", str(ability))
    assert result.returncode == 2
    assert "verification" in result.stdout
    assert "provenance" in result.stdout
    assert "lifecycle" in result.stdout


def test_register_rejects_duplicate_id(tmp_path: Path) -> None:
    ability = valid_ability()
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps(registry_document([ability])), encoding="utf-8")
    ability_path = tmp_path / "ability.json"
    ability_path.write_text(json.dumps(ability), encoding="utf-8")
    result = run_cli("--registry", str(registry), "register", str(ability_path))
    assert result.returncode == 2
    assert "already exists" in result.stdout


def test_register_rejects_malformed_id_without_mutating_registry(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    initial = registry_document()
    registry.write_text(json.dumps(initial, sort_keys=True), encoding="utf-8")
    ability = valid_ability("Bad Ability")
    ability_path = tmp_path / "ability.json"
    ability_path.write_text(json.dumps(ability), encoding="utf-8")

    result = run_cli("--registry", str(registry), "register", str(ability_path))

    assert result.returncode == 2
    assert "id must use lowercase" in result.stdout
    assert json.loads(registry.read_text(encoding="utf-8")) == initial


def test_register_rejects_empty_lifecycle_path(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps(registry_document()), encoding="utf-8")
    ability = valid_ability()
    ability["lifecycle"] = {"removal": ""}
    ability_path = tmp_path / "ability.json"
    ability_path.write_text(json.dumps(ability), encoding="utf-8")

    result = run_cli("--registry", str(registry), "register", str(ability_path))

    assert result.returncode == 2
    assert "rollback or removal path" in result.stdout


def test_register_rejects_invalid_existing_registry(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    malformed = registry_document()
    malformed["policy"] = {}
    registry.write_text(json.dumps(malformed), encoding="utf-8")
    ability_path = tmp_path / "ability.json"
    ability_path.write_text(json.dumps(valid_ability()), encoding="utf-8")

    result = run_cli("--registry", str(registry), "register", str(ability_path))

    assert result.returncode == 2
    assert "invalid registry" in result.stdout
    assert json.loads(registry.read_text(encoding="utf-8")) == malformed


def test_register_persists_valid_ability_and_list_reads_it(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps(registry_document()), encoding="utf-8")
    ability = valid_ability()
    ability_path = tmp_path / "ability.json"
    ability_path.write_text(json.dumps(ability), encoding="utf-8")

    registered = run_cli("--registry", str(registry), "register", str(ability_path))
    listed = run_cli("--registry", str(registry), "list")

    assert registered.returncode == 0
    assert "ABILITY_REGISTERED" in registered.stdout
    assert listed.returncode == 0
    assert "test/reusable/v1\tVERIFIED\tReusable test ability" in listed.stdout
    data = json.loads(registry.read_text(encoding="utf-8"))
    assert data["abilities"] == [ability]


def test_registry_policy_never_grants_authority() -> None:
    data = json.loads((ROOT / "automation" / "abilities" / "registry.json").read_text())
    assert data["policy"]["missing_capability"] == "BUILD_TEST_REGISTER_REUSE_WHEN_AUTHORIZED"
    assert data["policy"]["external_boundary"] == "RECORD_BLOCKER_AND_CONTINUE"
    assert "no_authority_expansion" in data["policy"]["requirements"]
