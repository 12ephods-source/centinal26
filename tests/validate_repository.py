#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/MASTER_PROJECT_TIMELINE.md",
    "schemas/job.schema.json",
    "schemas/audit.schema.json",
    "schemas/release.schema.json",
    "schemas/artifact.schema.json",
    "provenance/ARTIFACT_REGISTRY.json",
    "releases/BOOTSTRAP_STATE.json",
    "releases/1.0.0-rc3-ga-campaign/RELEASE_CERTIFICATE.json",
    "releases/1.0.0-rc4-converged/RC4_RELEASE_CONTROLLER.sh",
    "candidates/frost-automation-os-v1.0/IMPLEMENTATION_REPORT.md",
    "candidates/frost-automation-os-v1.0/CLEANROOM_RELEASE_VERIFY.json",
]
SCHEMAS = [
    "schemas/job.schema.json",
    "schemas/audit.schema.json",
    "schemas/release.schema.json",
    "schemas/artifact.schema.json",
]
REQUIRED_INVARIANT = "Intent → Authorization → Event/Queue → Capability Selection → Bounded Execution → Verification → Evidence/Audit → State Update → Controlled Evolution"
CLASSIFICATIONS = {"CANONICAL", "COMPATIBLE_MODULE", "EXPERIMENTAL", "SUPERSEDED", "REJECTED"}
VALIDATION_STATES = {"UNVERIFIED", "STATIC_VALIDATED", "HOST_VALIDATED", "REVIEW", "PASS", "FAIL"}
RC4_ORCHESTRATOR_SHA256 = "9d9b6a03e2ad7e3db23cf3dcb960bbeff3ab5424fecddeb81b98dfdae94b143a"
RC4_V6_BUNDLE_SHA256 = "0c861a444fcadb5f6fd33b758fd14df221dd9e4a07c522e207fb9983c13f4a93"


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(f"missing required files: {missing}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if REQUIRED_INVARIANT not in readme:
        raise SystemExit("canonical execution invariant missing from README")

    for rel in SCHEMAS:
        data = load(rel)
        if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise SystemExit(f"unexpected schema dialect in {rel}")
        if data.get("type") != "object":
            raise SystemExit(f"top-level schema type must be object: {rel}")

    registry = load("provenance/ARTIFACT_REGISTRY.json")
    artifacts = registry.get("artifacts") or []
    ids = [a.get("artifact_id") for a in artifacts]
    if len(ids) != len(set(ids)) or any(not x for x in ids):
        raise SystemExit("artifact registry contains missing or duplicate artifact_id values")

    by_id = {a["artifact_id"]: a for a in artifacts}
    for artifact in artifacts:
        if artifact.get("classification") not in CLASSIFICATIONS:
            raise SystemExit(f"invalid artifact classification: {artifact.get('artifact_id')}")
        validation = artifact.get("validation") or {}
        if validation.get("state") not in VALIDATION_STATES:
            raise SystemExit(f"invalid validation state: {artifact.get('artifact_id')}")
        if not isinstance(validation.get("physical_device_validated"), bool):
            raise SystemExit(f"physical_device_validated must be boolean: {artifact.get('artifact_id')}")
        if artifact.get("content_imported"):
            path = artifact.get("repository_path")
            if not path or not (ROOT / path).exists():
                raise SystemExit(f"imported artifact has missing repository path: {artifact.get('artifact_id')}")

    rc4 = by_id.get("ACP-RC4-ORCHESTRATOR") or {}
    if rc4.get("sha256") != RC4_ORCHESTRATOR_SHA256 or rc4.get("content_imported") is not False:
        raise SystemExit("RC4 orchestrator identity/provenance guard failed")

    v6 = by_id.get("ACP-RC4-V6-BUNDLE") or {}
    if v6.get("sha256") != RC4_V6_BUNDLE_SHA256 or v6.get("content_imported") is not False:
        raise SystemExit("RC4 embedded v6 bundle identity/provenance guard failed")

    candidate = by_id.get("FROST-AUTOMATION-OS-V1") or {}
    candidate_validation = candidate.get("validation") or {}
    if candidate.get("classification") != "COMPATIBLE_MODULE" or candidate_validation.get("state") != "HOST_VALIDATED":
        raise SystemExit("FROST Automation OS v1 candidate classification drift")
    if candidate_validation.get("physical_device_validated") is not False:
        raise SystemExit("host-validated candidate must not imply physical Android validation")

    cleanroom = load("candidates/frost-automation-os-v1.0/CLEANROOM_RELEASE_VERIFY.json")
    if cleanroom.get("status") != "PASS" or cleanroom.get("files") != 156:
        raise SystemExit("unexpected Frost Automation OS clean-room verification record")

    rc3_cert = load("releases/1.0.0-rc3-ga-campaign/RELEASE_CERTIFICATE.json")
    if rc3_cert.get("decision") != "REVIEW":
        raise SystemExit("RC3 historical certificate must remain REVIEW")
    missing_evidence = set((((rc3_cert.get("evaluation") or {}).get("reasons") or {}).get("missing_evidence") or []))
    expected_missing = {"ANDROID_VALIDATION", "ENDURANCE_VALIDATION", "DEVICE_SYNC_VALIDATION"}
    if not expected_missing.issubset(missing_evidence):
        raise SystemExit(f"RC3 missing-evidence record drifted: {sorted(missing_evidence)}")

    state = load("releases/BOOTSTRAP_STATE.json")
    if state.get("current_release_target") != "1.0.0-rc4-converged":
        raise SystemExit("current release target must remain RC4-converged until explicitly promoted")
    if state.get("current_release_status") != "REVIEW":
        raise SystemExit("RC4 release target must remain REVIEW at this gate")
    gates = state.get("gates") or {}
    forbidden_true = [
        "android_device_validated",
        "endurance_validated",
        "device_sync_validated",
        "native_candidate_certified",
        "explicit_human_promotion",
    ]
    accidentally_promoted = [g for g in forbidden_true if gates.get(g) is True]
    if accidentally_promoted:
        raise SystemExit(f"unearned promotion gates set true: {accidentally_promoted}")

    controller = (ROOT / "releases/1.0.0-rc4-converged/RC4_RELEASE_CONTROLLER.sh").read_text(encoding="utf-8")
    for marker in [
        "no host-for-physical substitution",
        "no automatic GA promotion",
        "BLOCK_PENDING_EXPLICIT_HUMAN_ACTION",
        "Physical evidence outer gate PASS. This is not GA promotion.",
    ]:
        if marker not in controller:
            raise SystemExit(f"RC4 controller safety marker missing: {marker}")

    print(f"Automation OS repository baseline: PASS ({len(artifacts)} registered artifacts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
