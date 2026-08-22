import importlib.util
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "automation/federation/project_federation.py"
spec = importlib.util.spec_from_file_location("project_federation", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_canonical_registry_is_valid():
    result = mod.validate_registry(ROOT / "automation/federation/projects.json")
    assert result.ok, result.errors
    assert {"automation", "cybersecurity", "physics"}.issubset(result.project_ids)


def test_unknown_dependency_fails_closed():
    source = json.loads((ROOT / "automation/federation/projects.json").read_text())
    source["projects"][0]["depends_on"] = ["missing-project"]
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "projects.json"
        path.write_text(json.dumps(source))
        result = mod.validate_registry(path)
    assert not result.ok
    assert "automation:unknown_dependency:missing-project" in result.errors


def test_missing_evidence_invariant_fails_closed():
    source = json.loads((ROOT / "automation/federation/projects.json").read_text())
    source["shared_invariants"].remove("host_evidence_never_substitutes_for_physical_device_evidence")
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "projects.json"
        path.write_text(json.dumps(source))
        result = mod.validate_registry(path)
    assert not result.ok
    assert any(x.startswith("missing_invariant:") for x in result.errors)
