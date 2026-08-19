import json
import sys


def avg(summary, mode, key):
    return float(summary[mode][key]["mean"])


with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["summary"]

baseline_pair = avg(summary, "baseline", "pair32_acc")
correct_pair = avg(summary, "correct_geo", "pair32_acc")
wrong_pair = avg(summary, "wrong_geo", "pair32_acc")
baseline_ood = avg(summary, "baseline", "ood32_acc")
correct_ood = avg(summary, "correct_geo", "ood32_acc")
baseline_inv = avg(summary, "baseline", "invariant32_acc")
correct_inv = avg(summary, "correct_geo", "invariant32_acc")

checks = {
    "correct_pair_gain": correct_pair > baseline_pair + 0.10,
    "correct_ood_gain": correct_ood > baseline_ood + 0.08,
    "correct_invariance_not_worse": correct_inv >= baseline_inv - 0.03,
    "wrong_pair_degrades": wrong_pair < baseline_pair - 0.05,
}
payload = {"checks": checks, "pass": all(checks.values())}
print(json.dumps(payload, indent=2))
sys.exit(0 if payload["pass"] else 1)
