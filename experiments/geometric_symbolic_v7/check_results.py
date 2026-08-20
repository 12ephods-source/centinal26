import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["summary"]

checks = {}
for task in ("c4", "v4"):
    task_summary = summary[task]
    checks[f"{task}_selects_correct_family"] = task_summary["correct_selection_rate"] == 1.0
    checks[f"{task}_correct_probability"] = (
        float(task_summary["correct_family_probability"]["mean"]) > 0.90
    )
    checks[f"{task}_fits_training"] = float(task_summary["train_acc"]["mean"]) > 0.98
    checks[f"{task}_near_pair"] = float(task_summary["near_pair"]["mean"]) > 0.95
    checks[f"{task}_far_pair"] = float(task_summary["far_pair"]["mean"]) > 0.95

payload = {"checks": checks, "pass": all(checks.values())}
print(json.dumps(payload, indent=2))
sys.exit(0 if payload["pass"] else 1)
