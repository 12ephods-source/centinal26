from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FederationResult:
    ok: bool
    errors: tuple[str, ...]
    project_ids: tuple[str, ...]


def validate_registry(path: Path) -> FederationResult:
    payload = json.loads(path.read_text())
    errors: list[str] = []
    projects = payload.get("projects", [])
    ids = [p.get("id") for p in projects]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_project_id")
    known = set(ids)
    for project in projects:
        pid = project.get("id")
        if not pid:
            errors.append("missing_project_id")
            continue
        if not project.get("trust_domain"):
            errors.append(f"{pid}:missing_trust_domain")
        if not project.get("state_authority"):
            errors.append(f"{pid}:missing_state_authority")
        for dep in project.get("depends_on", []):
            if dep not in known:
                errors.append(f"{pid}:unknown_dependency:{dep}")
            if dep == pid:
                errors.append(f"{pid}:self_dependency")
    required = {
        "automation",
        "cybersecurity",
        "physics",
    }
    missing = sorted(required - known)
    errors.extend(f"missing_required_project:{x}" for x in missing)
    invariants = set(payload.get("shared_invariants", []))
    required_invariants = {
        "no_information_bearing_transformation_without_provenance",
        "detection_and_mutation_are_separate_trust_domains",
        "host_evidence_never_substitutes_for_physical_device_evidence",
    }
    for invariant in sorted(required_invariants - invariants):
        errors.append(f"missing_invariant:{invariant}")
    return FederationResult(not errors, tuple(errors), tuple(sorted(known)))


def main() -> None:
    here = Path(__file__).resolve().parent
    result = validate_registry(here / "projects.json")
    print(json.dumps({"ok": result.ok, "errors": result.errors, "project_ids": result.project_ids}, indent=2))
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
