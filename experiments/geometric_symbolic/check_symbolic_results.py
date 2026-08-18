import json
import sys


def avg(summary, mode, key):
    return float(summary[mode][key]["mean"])


with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["summary"]

b_pair = avg(summary, "baseline", "pair16_acc")
g_pair = avg(summary, "correct_geo", "pair16_acc")
w_pair = avg(summary, "wrong_geo", "pair16_acc")
b_ood = avg(summary, "baseline", "ood16_acc")
g_ood = avg(summary, "correct_geo", "ood16_acc")
b_inv = avg(summary, "baseline", "invariant16_acc")
g_inv = avg(summary, "correct_geo", "invariant16_acc")

checks = {
    "correct_pair_gain": g_pair > b_pair + 0.10,
    "correct_ood_gain": g_ood > b_ood + 0.05,
    "correct_invariant_not_worse": g_inv >= b_inv - 0.03,
    "wrong_pair_degrades": w_pair < b_pair - 0.05,
}
payload = {"checks": checks, "pass": all(checks.values())}
print(json.dumps(payload, indent=2))
sys.exit(0 if payload["pass"] else 1)
