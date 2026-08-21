import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX = ROOT / "automation" / "SOURCE_INDEX.json"
PROJECT_STATE = ROOT / "automation" / "PROJECT_STATE.json"
REGISTRY = ROOT / "deploy" / "automation_os" / "registry.json"


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_source_index_contract():
    index = load(INDEX)
    state = load(PROJECT_STATE)
    registry = load(REGISTRY)

    assert index["repository"] == "12ephods-source/centinal26"
    assert index["canonical_branch"] == "main"
    assert state["project"]["canonical_branch"] == "main"
    assert index["canonical_physical_gate"]["tracker_issue"] == 208
    assert (
        index["canonical_physical_gate"]["qualified_source_commit"]
        == state["physical_gate"]["qualified_source_commit"]
        == "9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483"
    )
    assert registry["integrity_policy"]["fail_closed"] is True


def test_canonical_paths_exist():
    index = load(INDEX)
    required = [
        *index["canonical_state_records"],
        index["canonical_installer"]["module_manager"],
        index["canonical_installer"]["module_registry"],
        index["canonical_installer"]["current_termux_installer"],
        index["canonical_physical_gate"]["commissioning_runner"],
        index["canonical_physical_gate"]["controller_verifier"],
        index["canonical_physical_gate"]["heartbeat"],
        index["canonical_runtime"]["executor_registry"],
    ]
    missing = [path for path in required if not (ROOT / path).exists()]
    assert missing == []


def test_source_classes_do_not_promote_candidates():
    index = load(INDEX)
    candidates = set(index["open_automation_candidates"])
    superseded = set(index["superseded_or_redundant_prs"])
    external = set(index["external_project_prs_excluded_from_automation_runtime"])

    assert candidates.isdisjoint(superseded)
    assert candidates.isdisjoint(external)
    assert {"175", "207", "211", "215", "231"} <= superseded
    assert {"128", "130"} <= external
    assert "164" in candidates


def test_cleanup_policy_preserves_provenance():
    index = load(INDEX)
    policy = index["policy"]
    legacy = index["legacy_source_policy"]

    assert "merged to canonical main" in policy["production_rule"]
    assert "candidates" in policy["open_pr_rule"]
    assert "provenance" in policy["history_rule"]
    assert "Do not delete" in legacy["termux_versioned_scripts"]
    assert "not source control" in legacy["generated_artifacts"]
