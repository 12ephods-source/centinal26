import json
import sys


def avg(summary, mode, key):
    return float(summary[mode][key]["mean"])


with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["summary"]

correct_near = avg(summary, "correct_c4", "near_pair")
correct_far = avg(summary, "correct_c4", "far_pair")
baseline_near = avg(summary, "baseline", "near_pair")
baseline_far = avg(summary, "baseline", "far_pair")
generic_near = avg(summary, "generic", "near_pair")
generic_far = avg(summary, "generic", "far_pair")
wrong_near = avg(summary, "wrong_v4", "near_pair")
wrong_far = avg(summary, "wrong_v4", "far_pair")
correct_c4_residual = avg(summary, "correct_c4", "c4_residual")
wrong_c4_residual = avg(summary, "wrong_v4", "c4_residual")

checks = {
    "correct_beats_baseline_near": correct_near > baseline_near + 0.10,
    "correct_beats_generic_near": correct_near > generic_near + 0.10,
    "correct_beats_baseline_far": correct_far > baseline_far + 0.10,
    "correct_beats_generic_far": correct_far > generic_far + 0.10,
    "correct_beats_wrong_near": correct_near > wrong_near + 0.10,
    "correct_beats_wrong_far": correct_far > wrong_far + 0.10,
    "correct_relation_is_more_c4": correct_c4_residual < 0.75 * wrong_c4_residual,
}
payload = {"checks": checks, "pass": all(checks.values())}
print(json.dumps(payload, indent=2))
sys.exit(0 if payload["pass"] else 1)
