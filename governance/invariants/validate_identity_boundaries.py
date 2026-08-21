import json
from pathlib import Path

POLICY = Path(__file__).with_name("organizer_bluetooth_identity_boundary.json")


def main() -> None:
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    assert data["invariant_id"] == "NO_IMPLICIT_ORGANIZER_BLUETOOTH_IDENTITY_MERGE"
    assert data["severity"] == "BLOCKING"

    org = set(data["namespaces"]["organizer"])
    bt = set(data["namespaces"]["bluetooth"])
    assert org
    assert bt
    assert org.isdisjoint(bt), f"identity namespace overlap: {sorted(org & bt)}"

    binding = data["permitted_cross_domain_binding"]
    assert binding["method"] == "explicit_relationship_or_provenance_edge"
    requirements = set(binding["requirements"])
    assert "independent source evidence" in requirements
    assert "explicit relationship type" in requirements
    assert "source identifiers preserved without replacement" in requirements

    forbidden = "\n".join(data["forbidden"]).lower()
    assert "human/operator identity" in forbidden
    assert "device_validated" in forbidden
    assert "textually equal" in forbidden

    gates = data["physical_gate_domains"]
    assert gates["organizer_automation"]["tracker"] == "github_issue_208"
    assert gates["bluetooth_guard"]["tracker"] == "github_issue_261"
    assert gates["organizer_automation"]["device_validated"] == "independent"
    assert gates["bluetooth_guard"]["bluetooth_device_validated"] == "independent"
    assert gates["bluetooth_guard"]["bluetooth_persistent_validated"] == "independent"

    assert "unbound" in data["fail_closed_rule"].lower()
    assert "not proof of the human operator" in data["epistemic_boundary"].lower()
    print("PASS: organizer/bluetooth identity domains are separate and fail closed")


if __name__ == "__main__":
    main()
