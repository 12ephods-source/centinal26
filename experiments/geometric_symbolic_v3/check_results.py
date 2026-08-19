import json
import sys


def avg(summary, mode, key):
    return float(summary[mode][key]["mean"])


with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

summary = payload["summary"]
rows = payload["rows"]

baseline_pair = avg(summary, "baseline", "pair32_acc")
correct_pair = avg(summary, "correct_geo", "pair32_acc")
wrong_pair = avg(summary, "wrong_geo", "pair32_acc")
baseline_ood = avg(summary, "baseline", "ood32_acc")
correct_ood = avg(summary, "correct_geo", "ood32_acc")
wrong_ood = avg(summary, "wrong_geo", "ood32_acc")
baseline_inv = avg(summary, "baseline", "invariant32_acc")
correct_inv = avg(summary, "correct_geo", "invariant32_acc")

by_seed = {}
for row in rows:
    by_seed.setdefault(int(row["seed"]), {})[row["mode"]] = row

seed_directional = []
for seed, modes in sorted(by_seed.items()):
    ok = (
        modes["correct_geo"]["pair32_acc"] > modes["baseline"]["pair32_acc"] + 0.10
        and modes["correct_geo"]["pair32_acc"] > modes["wrong_geo"]["pair32_acc"] + 0.10
    )
    seed_directional.append({"seed": seed, "pass": ok})

checks = {
    "correct_pair_gain_vs_baseline": correct_pair > baseline_pair + 0.20,
    "correct_ood_gain_vs_baseline": correct_ood > baseline_ood + 0.15,
    "correct_invariance_not_worse": correct_inv >= baseline_inv - 0.03,
    "correct_pair_exceeds_wrong": correct_pair > wrong_pair + 0.20,
    "correct_ood_exceeds_wrong": correct_ood > wrong_ood + 0.15,
    "seed_direction_consistency": sum(item["pass"] for item in seed_directional) >= 2,
}
result = {
    "checks": checks,
    "seed_directional": seed_directional,
    "means": {
        "baseline_pair32": baseline_pair,
        "correct_pair32": correct_pair,
        "wrong_pair32": wrong_pair,
        "baseline_ood32": baseline_ood,
        "correct_ood32": correct_ood,
        "wrong_ood32": wrong_ood,
        "baseline_invariant32": baseline_inv,
        "correct_invariant32": correct_inv,
    },
    "pass": all(checks.values()),
}
print(json.dumps(result, indent=2))
sys.exit(0 if result["pass"] else 1)
