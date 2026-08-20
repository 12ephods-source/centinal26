import json
import sys


def avg(summary, mode, key):
    return float(summary[mode][key]["mean"])


with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["summary"]

baseline_acc = avg(summary, "baseline", "near_acc")
correct_acc = avg(summary, "correct_geo", "near_acc")
wrong_acc = avg(summary, "wrong_geo", "near_acc")
baseline_pair = avg(summary, "baseline", "near_pair")
correct_pair = avg(summary, "correct_geo", "near_pair")
wrong_pair = avg(summary, "wrong_geo", "near_pair")
baseline_inv = avg(summary, "baseline", "near_invariant")
correct_inv = avg(summary, "correct_geo", "near_invariant")

checks = {
    "correct_near_accuracy_gain": correct_acc > baseline_acc + 0.10,
    "correct_near_pair_gain": correct_pair > baseline_pair + 0.10,
    "correct_invariance_not_worse": correct_inv >= baseline_inv - 0.03,
    "wrong_near_accuracy_degrades": wrong_acc < baseline_acc - 0.05,
    "wrong_near_pair_degrades": wrong_pair < baseline_pair - 0.05,
}
payload = {"checks": checks, "pass": all(checks.values())}
print(json.dumps(payload, indent=2))
sys.exit(0 if payload["pass"] else 1)
