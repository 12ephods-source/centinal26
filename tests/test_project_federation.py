import importlib.util
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "automation/federation/project_federation.py"
REGISTRY = ROOT / "automation/federation/projects.json"
GOALS = ROOT / "automation/account_goals/GOALS.json"
spec = importlib.util.spec_from_file_location("project_federation", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _validate(payload):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "projects.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return mod.validate_registry(path, GOALS)


def test_canonical_registry_is_valid_and_owns_every_goal_once():
    result = mod.validate_registry(REGISTRY, GOALS)
    assert result.ok, result.errors
    assert set(mod.REQUIRED_PROJECTS).issubset(result.project_ids)
    assert set(mod.REQUIRED_COMPONENTS).issubset(result.component_ids)

    ledger = json.loads(GOALS.read_text(encoding="utf-8"))
    ledger_goal_ids = {goal["id"] for goal in ledger["goals"]}
    assert set(dict(result.goal_owners)) == ledger_goal_ids
    assert len(result.goal_owners) == 30


def test_unknown_dependency_fails_closed():
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source["projects"][0]["depends_on"] = ["missing-project"]
    result = _validate(source)
    assert not result.ok
    assert "automation:unknown_dependency:missing-project" in result.errors


def test_dependency_cycle_fails_closed():
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    automation = next(project for project in source["projects"] if project["id"] == "automation")
    automation["depends_on"] = ["agent_fabric"]
    result = _validate(source)
    assert not result.ok
    assert any(error.startswith("dependency_cycle:") for error in result.errors)


def test_missing_evidence_invariant_fails_closed():
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source["shared_invariants"].remove(
        "host_evidence_never_substitutes_for_physical_device_evidence"
    )
    result = _validate(source)
    assert not result.ok
    assert any(error.startswith("missing_invariant:") for error in result.errors)


def test_unknown_component_fails_closed():
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    project = next(project for project in source["projects"] if project["id"] == "physics")
    project["component_ids"].append("C99")
    result = _validate(source)
    assert not result.ok
    assert "physics:unknown_component:C99" in result.errors


def test_missing_goal_owner_fails_closed():
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for project in source["projects"]:
        if "G15" in project["goal_ids"]:
            project["goal_ids"].remove("G15")
    result = _validate(source)
    assert not result.ok
    assert "missing_goal_owner:G15" in result.errors


def test_duplicate_goal_owner_fails_closed():
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    project = next(project for project in source["projects"] if project["id"] == "physics")
    project["goal_ids"].append("G15")
    result = _validate(source)
    assert not result.ok
    assert "duplicate_goal_owner:G15:physics,test_a_theory" in result.errors


def test_unknown_goal_id_fails_closed():
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    project = next(project for project in source["projects"] if project["id"] == "automation")
    project["goal_ids"].append("G99")
    result = _validate(source)
    assert not result.ok
    assert "unknown_goal_id:G99" in result.errors


def test_ambiguous_alias_fails_closed():
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    physics = next(project for project in source["projects"] if project["id"] == "physics")
    cybersecurity = next(
        project for project in source["projects"] if project["id"] == "cybersecurity"
    )
    physics["aliases"].append(cybersecurity["aliases"][0])
    result = _validate(source)
    assert not result.ok
    assert any(error.startswith("ambiguous_project_label:") for error in result.errors)


def test_unknown_shared_component_owner_fails_closed():
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source["shared_components"][0]["owner_project_id"] = "missing-project"
    result = _validate(source)
    assert not result.ok
    assert "C01:unknown_owner_project:missing-project" in result.errors
