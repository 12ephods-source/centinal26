import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["summary"]

checks = {}
for task in ("c4", "v4"):
    task_summary = summary[task]
    checks[f"{task}_family"] = task_summary["correct_family_rate"] == 1.0
    checks[f"{task}_behavior_equivalence"] = (
        task_summary["behavioral_equivalence_rate"] == 1.0
    )
    checks[f"{task}_selection_probability"] = (
        float(task_summary["selection_probability"]["mean"]) > 0.90
    )
    checks[f"{task}_train_accuracy"] = float(task_summary["train_acc"]["mean"]) > 0.99
    checks[f"{task}_near_pair"] = float(task_summary["near_pair"]["mean"]) > 0.99
    checks[f"{task}_far_pair"] = float(task_summary["far_pair"]["mean"]) > 0.99

payload = {"checks": checks, "pass": all(checks.values())}
print(json.dumps(payload, indent=2))
sys.exit(0 if payload["pass"] else 1)
