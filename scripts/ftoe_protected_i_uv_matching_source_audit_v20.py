from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "physics/ftoe/protected_i_uv_matching_source_audit_v20.json"


def main() -> int:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    checks = data["checks"]
    expected = {
        "so6_reference_has_two_pnGB_doublets": True,
        "so6_reference_has_explicit_ftoe_so10_heavy_matching": False,
        "so11_so10_reference_has_so10_organized_pnGB_sector": True,
        "so11_so10_reference_has_two_independent_electroweak_doublet_roles": False,
        "existing_reference_closes_both_requirements": False,
    }
    ok = checks == expected
    ok &= data["verdict"] == "UNRESOLVED_UV_MATCHING_BIFURCATION"
    ok &= data["scientific_status"] == "REVIEW_FAIL_CLOSED"
    ok &= bool(data["smallest_missing_input"].strip())
    result = {
        "execution_pass": bool(ok),
        "scientific_pass": False,
        "verdict": data["verdict"],
        "checks": checks,
        "smallest_missing_input": data["smallest_missing_input"],
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
