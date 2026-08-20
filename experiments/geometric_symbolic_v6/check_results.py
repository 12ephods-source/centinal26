import json
import sys


def avg(summary, mode, key):
    return float(summary[mode][key]["mean"])


with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["summary"]

correct_train = avg(summary, "exact_c4", "train_acc")
correct_near = avg(summary, "exact_c4", "near_pair")
correct_far = avg(summary, "exact_c4", "far_pair")
wrong_far = avg(summary, "wrong_v4", "far_pair")
generic_far = avg(summary, "generic_fixed", "far_pair")
independent_far = avg(summary, "independent_so4", "far_pair")
wrong_near = avg(summary, "wrong_v4", "near_pair")
generic_near = avg(summary, "generic_fixed", "near_pair")
independent_near = avg(summary, "independent_so4", "near_pair")

checks = {
    "exact_c4_fits_training": correct_train > 0.98,
    "exact_c4_near_pair": correct_near > 0.95,
    "exact_c4_far_pair": correct_far > 0.95,
    "exact_c4_beats_wrong_near": correct_near > wrong_near + 0.10,
    "exact_c4_beats_generic_near": correct_near > generic_near + 0.10,
    "exact_c4_beats_independent_near": correct_near > independent_near + 0.10,
    "exact_c4_beats_wrong_far": correct_far > wrong_far + 0.20,
    "exact_c4_beats_generic_far": correct_far > generic_far + 0.20,
    "exact_c4_beats_independent_far": correct_far > independent_far + 0.20,
}
payload = {"checks": checks, "pass": all(checks.values())}
print(json.dumps(payload, indent=2))
sys.exit(0 if payload["pass"] else 1)
