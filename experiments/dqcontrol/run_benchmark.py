import hashlib
import json
from pathlib import Path

from core import benchmark_all

ROOT = Path(__file__).resolve().parent
state_bytes = (ROOT / "theory_state.json").read_bytes()
state_sha = hashlib.sha256(state_bytes).hexdigest()
results = benchmark_all()
engineering_pass = all(results["gates"].values())
record = {
    "engine_version": "FROST-DQCONTROL-v0.1.0",
    "theory_state_sha256": state_sha,
    "software_gate": "PASS",
    "numerical_gate": "PASS" if engineering_pass else "FAIL",
    "prior_art_gate": "REVIEW",
    "hardware_gate": "NOT_TESTED",
    "new_physics_gate": "NOT_TESTED",
    "overall": "REVIEW" if engineering_pass else "FAIL",
    "results": results,
}
art = ROOT / "artifacts"
art.mkdir(exist_ok=True)
(art / "benchmark_results.json").write_text(json.dumps(results, indent=2, sort_keys=True))
(art / "certification_record.json").write_text(json.dumps(record, indent=2, sort_keys=True))
print(json.dumps(record, indent=2, sort_keys=True))
if not engineering_pass:
    raise SystemExit(2)
