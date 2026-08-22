from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_GOALS = Path(__file__).resolve().parents[1] / "account_goals" / "GOALS.json"

REQUIRED_PROJECTS = {
    "automation",
    "agent_fabric",
    "cybersecurity",
    "provenance_recovery",
    "dedupe_organizer",
    "aaard",
    "conversation_intelligence",
    "epistemic_guard",
    "physics",
    "test_a_theory",
    "openquestrpg",
    "creative_canon",
    "productization",
}
REQUIRED_COMPONENTS = {"C01", "C02", "C03", "C04", "C05"}
REQUIRED_INVARIANTS = {
    "no_information_bearing_transformation_without_provenance",
    "detection_and_mutation_are_separate_trust_domains",
    "host_evidence_never_substitutes_for_physical_device_evidence",
    "signatures_and_hashes_attest_integrity_not_semantic_truth",
    "projections_are_rebuildable_not_authoritative",
    "completion_claims_are_release_scoped_and_requalifiable",
    "every_account_goal_has_exactly_one_canonical_project_owner",
    "legacy_names_resolve_to_one_canonical_owner_without_recreating_duplicate_state",
}


@dataclass(frozen=True)
class FederationResult:
    ok: bool
    errors: tuple[str, ...]
    project_ids: tuple[str, ...]
    component_ids: tuple[str, ...]
    goal_owners: tuple[tuple[str, str], ...]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}:root_not_object")
    return payload


def _dependency_cycle(graph: dict[str, list[str]]) -> tuple[str, ...] | None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, path: list[str]) -> tuple[str, ...] | None:
        if node in visiting:
            start = path.index(node)
            return tuple(path[start:] + [node])
        if node in visited:
            return None
        visiting.add(node)
        path.append(node)
        for dep in graph.get(node, []):
            cycle = visit(dep, path)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        cycle = visit(node, [])
        if cycle:
            return cycle
    return None


def validate_registry(
    path: Path,
    goals_path: Path | None = None,
) -> FederationResult:
    payload = _load_json(path)
    errors: list[str] = []

    if payload.get("schema_version") != 2:
        errors.append("unsupported_schema_version")
    if not payload.get("portfolio_id"):
        errors.append("missing_portfolio_id")
    if payload.get("canonical_control_plane") != "12ephods-source/centinal26":
        errors.append("unexpected_canonical_control_plane")
    if payload.get("combination_model") != "federated_modules_with_single_goal_ownership":
        errors.append("unexpected_combination_model")

    projects = payload.get("projects", [])
    if not isinstance(projects, list):
        errors.append("projects_not_list")
        projects = []
    ids = [project.get("id") for project in projects if isinstance(project, dict)]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_project_id")
    known_projects = {pid for pid in ids if isinstance(pid, str) and pid}
    for missing in sorted(REQUIRED_PROJECTS - known_projects):
        errors.append(f"missing_required_project:{missing}")

    components = payload.get("shared_components", [])
    if not isinstance(components, list):
        errors.append("shared_components_not_list")
        components = []
    component_ids = [
        component.get("id")
        for component in components
        if isinstance(component, dict)
    ]
    if len(component_ids) != len(set(component_ids)):
        errors.append("duplicate_component_id")
    known_components = {
        cid for cid in component_ids if isinstance(cid, str) and cid
    }
    for missing in sorted(REQUIRED_COMPONENTS - known_components):
        errors.append(f"missing_required_component:{missing}")

    for component in components:
        if not isinstance(component, dict):
            errors.append("component_not_object")
            continue
        cid = component.get("id")
        owner = component.get("owner_project_id")
        if not cid:
            errors.append("missing_component_id")
            continue
        if owner not in known_projects:
            errors.append(f"{cid}:unknown_owner_project:{owner}")
        if not component.get("purpose"):
            errors.append(f"{cid}:missing_purpose")

    goal_owners: defaultdict[str, list[str]] = defaultdict(list)
    label_owners: defaultdict[str, set[str]] = defaultdict(set)
    graph: dict[str, list[str]] = {}

    for project in projects:
        if not isinstance(project, dict):
            errors.append("project_not_object")
            continue
        pid = project.get("id")
        if not pid:
            errors.append("missing_project_id")
            continue
        if not project.get("name"):
            errors.append(f"{pid}:missing_name")
        if not project.get("trust_domain"):
            errors.append(f"{pid}:missing_trust_domain")
        if not project.get("state_authority"):
            errors.append(f"{pid}:missing_state_authority")

        deps = project.get("depends_on", [])
        if not isinstance(deps, list):
            errors.append(f"{pid}:depends_on_not_list")
            deps = []
        graph[pid] = [dep for dep in deps if isinstance(dep, str)]
        for dep in deps:
            if dep not in known_projects:
                errors.append(f"{pid}:unknown_dependency:{dep}")
            if dep == pid:
                errors.append(f"{pid}:self_dependency")

        project_components = project.get("component_ids", [])
        if not isinstance(project_components, list):
            errors.append(f"{pid}:component_ids_not_list")
            project_components = []
        if len(project_components) != len(set(project_components)):
            errors.append(f"{pid}:duplicate_component_id")
        for cid in project_components:
            if cid not in known_components:
                errors.append(f"{pid}:unknown_component:{cid}")

        project_goals = project.get("goal_ids", [])
        if not isinstance(project_goals, list):
            errors.append(f"{pid}:goal_ids_not_list")
            project_goals = []
        if len(project_goals) != len(set(project_goals)):
            errors.append(f"{pid}:duplicate_goal_id")
        for goal_id in project_goals:
            if isinstance(goal_id, str):
                goal_owners[goal_id].append(pid)
            else:
                errors.append(f"{pid}:invalid_goal_id:{goal_id!r}")

        labels = [
            pid,
            project.get("name"),
            *project.get("aliases", []),
            *project.get("related_legacy_names", []),
        ]
        for label in labels:
            if not isinstance(label, str) or not label.strip():
                errors.append(f"{pid}:invalid_project_label")
                continue
            label_owners[label.strip().casefold()].add(pid)

    cycle = _dependency_cycle(graph)
    if cycle:
        errors.append("dependency_cycle:" + "->".join(cycle))

    for label, owners in sorted(label_owners.items()):
        if len(owners) > 1:
            errors.append(
                "ambiguous_project_label:"
                + label
                + ":"
                + ",".join(sorted(owners))
            )

    goals_file = goals_path or DEFAULT_GOALS
    try:
        goal_payload = _load_json(goals_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"cannot_load_goal_ledger:{exc}")
        ledger_goals: set[str] = set()
    else:
        raw_goals = goal_payload.get("goals", [])
        ledger_ids = [
            goal.get("id")
            for goal in raw_goals
            if isinstance(goal, dict) and isinstance(goal.get("id"), str)
        ]
        if len(ledger_ids) != len(set(ledger_ids)):
            errors.append("duplicate_goal_id_in_ledger")
        ledger_goals = set(ledger_ids)

    for goal_id in sorted(ledger_goals):
        owners = goal_owners.get(goal_id, [])
        if not owners:
            errors.append(f"missing_goal_owner:{goal_id}")
        elif len(owners) > 1:
            errors.append(
                f"duplicate_goal_owner:{goal_id}:{','.join(sorted(owners))}"
            )
    for goal_id in sorted(set(goal_owners) - ledger_goals):
        errors.append(f"unknown_goal_id:{goal_id}")

    invariants = set(payload.get("shared_invariants", []))
    for invariant in sorted(REQUIRED_INVARIANTS - invariants):
        errors.append(f"missing_invariant:{invariant}")

    canonical_goal_owners = tuple(
        sorted(
            (goal_id, owners[0])
            for goal_id, owners in goal_owners.items()
            if len(owners) == 1 and goal_id in ledger_goals
        )
    )
    return FederationResult(
        ok=not errors,
        errors=tuple(errors),
        project_ids=tuple(sorted(known_projects)),
        component_ids=tuple(sorted(known_components)),
        goal_owners=canonical_goal_owners,
    )


def main() -> None:
    here = Path(__file__).resolve().parent
    result = validate_registry(here / "projects.json")
    print(
        json.dumps(
            {
                "ok": result.ok,
                "errors": result.errors,
                "project_ids": result.project_ids,
                "component_ids": result.component_ids,
                "goal_owner_count": len(result.goal_owners),
                "goal_owners": dict(result.goal_owners),
            },
            indent=2,
            sort_keys=True,
        )
    )
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
