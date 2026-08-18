import json
import sys


def avg(summary, mode, key):
    return float(summary[mode][key]["mean"])


with open(sys.argv[1], encoding="utf-8") as file_handle:
    summary = json.load(file_handle)["summary"]

baseline_mse = avg(summary, "baseline", "ood16_mse")
correct_mse = avg(summary, "correct_geo", "ood16_mse")
wrong_mse = avg(summary, "wrong_geo", "ood16_mse")
baseline_exact = avg(summary, "baseline", "exact16")
correct_exact = avg(summary, "correct_geo", "exact16")
baseline_cv = avg(summary, "baseline", "delta_cv")
correct_cv = avg(summary, "correct_geo", "delta_cv")

checks = {
    "correct_mse": correct_mse < 0.80 * baseline_mse,
    "correct_exact": correct_exact > baseline_exact + 0.20,
    "correct_cv": correct_cv < baseline_cv,
    "wrong_mse": wrong_mse > 1.05 * baseline_mse,
}
print(json.dumps({"checks": checks, "pass": all(checks.values())}, indent=2))
sys.exit(0 if all(checks.values()) else 1)
