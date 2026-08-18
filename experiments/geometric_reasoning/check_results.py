#!/usr/bin/env python3
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    s = json.load(f)["summary"]

def avg(mode, key):
    return float(s[mode][key]["mean"])

b_mse = avg("baseline", "ood16_mse")
g_mse = avg("correct_geo", "ood16_mse")
w_mse = avg("wrong_geo", "ood16_mse")
b_exact = avg("baseline", "exact16")
g_exact = avg("correct_geo", "exact16")
b_cv = avg("baseline", "delta_cv")
g_cv = avg("correct_geo", "delta_cv")

checks = {
    "correct_mse": g_mse < 0.80 * b_mse,
    "correct_exact": g_exact > b_exact + 0.20,
    "correct_cv": g_cv < b_cv,
    "wrong_mse": w_mse > 1.05 * b_mse,
}
print(json.dumps({"checks": checks, "pass": all(checks.values())}, indent=2))
sys.exit(0 if all(checks.values()) else 1)
