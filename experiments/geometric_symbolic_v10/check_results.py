import json
import sys


def avg(summary, mode, key):
    return float(summary[mode][key]["mean"])


with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["summary"]

structured_train = avg(summary, "exact_c4", "train_pair")
structured_ground = avg(summary, "exact_c4", "token_grounding_acc")
structured_near = avg(summary, "exact_c4", "near_pair")
structured_far = avg(summary, "exact_c4", "far_pair")
wrong_far = avg(summary, "wrong_v4", "far_pair")
gru_far = avg(summary, "gru", "far_pair")
structured_params = int(summary["exact_c4"]["parameter_count"])
gru_params = int(summary["gru"]["parameter_count"])

checks = {
    "structured_fits_paired_training": structured_train > 0.95,
    "latent_grounding": structured_ground > 0.98,
    "structured_near_pair": structured_near > 0.95,
    "structured_far_pair": structured_far > 0.90,
    "structured_beats_wrong_far": structured_far > wrong_far + 0.20,
    "structured_beats_gru_far": structured_far > gru_far + 0.20,
    "structured_not_larger_than_gru": structured_params <= gru_params,
}
payload = {"checks": checks, "pass": all(checks.values())}
print(json.dumps(payload, indent=2))
sys.exit(0 if payload["pass"] else 1)
