import json
import sys


def avg(summary, mode, key):
    return float(summary[mode][key]["mean"])


with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["summary"]

baseline_acc = avg(summary, "baseline", "ood64_acc")
correct_acc = avg(summary, "correct_geo", "ood64_acc")
baseline_pair = avg(summary, "baseline", "pair64_acc")
correct_pair = avg(summary, "correct_geo", "pair64_acc")
baseline_inv = avg(summary, "baseline", "invariant64_acc")
correct_inv = avg(summary, "correct_geo", "invariant64_acc")
baseline_loss = avg(summary, "baseline", "ood64_logistic_loss")
correct_loss = avg(summary, "correct_geo", "ood64_logistic_loss")
wrong_loss = avg(summary, "wrong_geo", "ood64_logistic_loss")
baseline_margin = avg(summary, "baseline", "pair64_margin")
correct_margin = avg(summary, "correct_geo", "pair64_margin")

checks = {
    "correct_ood64_gain": correct_acc > baseline_acc + 0.10,
    "correct_pair64_gain": correct_pair > baseline_pair + 0.10,
    "correct_invariance_not_worse": correct_inv >= baseline_inv - 0.05,
    "correct_loss_improves": correct_loss < 0.80 * baseline_loss,
    "wrong_loss_degrades": wrong_loss > 1.05 * baseline_loss,
    "correct_pair_margin_improves": correct_margin > baseline_margin + 0.10,
}
payload = {"checks": checks, "pass": all(checks.values())}
print(json.dumps(payload, indent=2))
sys.exit(0 if payload["pass"] else 1)
