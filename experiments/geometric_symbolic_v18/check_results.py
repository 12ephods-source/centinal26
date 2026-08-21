from __future__ import annotations

import json
import sys
from statistics import mean

PATH = sys.argv[1] if len(sys.argv) > 1 else "results.json"
with open(PATH, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

rows = payload["rows"]
exact = {r["seed"]: r for r in rows if r["mode"] == "exact_c4"}
wrong = {r["seed"]: r for r in rows if r["mode"] == "wrong_v4"}
gru = {r["seed"]: r for r in rows if r["mode"] == "gru"}
seeds = sorted(exact)

reliable = sum(bool(exact[s]["reliable_exact"]) for s in seeds)
wrong_wins = sum(exact[s]["far_pair"] - wrong[s]["far_pair"] > 0.20 for s in seeds)
gru_wins = sum(exact[s]["far_pair"] - gru[s]["far_pair"] > 0.20 for s in seeds)

exact_far = mean(exact[s]["far_pair"] for s in seeds)
wrong_far = mean(wrong[s]["far_pair"] for s in seeds)
gru_far = mean(gru[s]["far_pair"] for s in seeds)
exact_ground = mean(exact[s]["token_grounding_acc"] for s in seeds)

checks = {
    "fresh_seed_contract": seeds == list(range(170, 182)),
    "anchor_rate_frozen_10pct": all(abs(r.get("anchor_rate", -1) - 0.10) < 1e-12 for r in rows),
    "exact_reliable_at_least_10_of_12": reliable >= 10,
    "exact_mean_grounding_gt_0_98": exact_ground > 0.98,
    "exact_mean_far_pair_gt_0_90": exact_far > 0.90,
    "exact_beats_wrong_by_0_20_on_at_least_10_of_12": wrong_wins >= 10,
    "exact_beats_gru_by_0_20_on_at_least_10_of_12": gru_wins >= 10,
    "exact_mean_far_margin_over_wrong_gt_0_20": exact_far - wrong_far > 0.20,
    "exact_mean_far_margin_over_gru_gt_0_20": exact_far - gru_far > 0.20,
    "structured_not_larger_than_gru": payload["summary"]["exact_c4"]["parameter_count"] <= payload["summary"]["gru"]["parameter_count"],
}

verdict = {
    "checks": checks,
    "counts": {
        "reliable_exact": reliable,
        "matched_seeds": len(seeds),
        "per_seed_margin_gt_0_20_vs_wrong": wrong_wins,
        "per_seed_margin_gt_0_20_vs_gru": gru_wins,
    },
    "means": {
        "exact_grounding": exact_ground,
        "exact_far_pair": exact_far,
        "wrong_far_pair": wrong_far,
        "gru_far_pair": gru_far,
    },
    "pass": all(checks.values()),
}
print(json.dumps(verdict, indent=2, sort_keys=True))
raise SystemExit(0 if verdict["pass"] else 1)
