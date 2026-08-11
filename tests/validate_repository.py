#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md",
    "docs/ARCHITECTURE.md",
    "schemas/job.schema.json",
    "schemas/audit.schema.json",
    "schemas/release.schema.json",
]
REQUIRED_INVARIANT = "Intent → Authorization → Event/Queue → Capability Selection → Bounded Execution → Verification → Evidence/Audit → State Update → Controlled Evolution"


def main() -> int:
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(f"missing required files: {missing}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if REQUIRED_INVARIANT not in readme:
        raise SystemExit("canonical execution invariant missing from README")

    for rel in ["schemas/job.schema.json", "schemas/audit.schema.json", "schemas/release.schema.json"]:
        data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise SystemExit(f"unexpected schema dialect in {rel}")
        if data.get("type") != "object":
            raise SystemExit(f"top-level schema type must be object: {rel}")

    print("Automation OS repository baseline: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
