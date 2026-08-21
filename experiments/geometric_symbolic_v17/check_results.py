from __future__ import annotations

import argparse
import json
import math

LOW = "0.06250"
HIGH = "0.06875"
ALPHA = 0.05


def one_sided_mcnemar_p(high_only: int, low_only: int) -> float:
    discordant = high_only + low_only
    if discordant == 0:
        return 1.0
    return sum(math.comb(discordant, k) for k in range(high_only, discordant + 1)) / (2 ** discordant)


def exact_rows(payload, dose):
    return {
        row["seed"]: row
        for row in payload["rows"]
        if f'{row["dose"]:.5f}' == dose and row["mode"] == "exact_c4"
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results")
    args = parser.parse_args()
    with open(args.results, encoding="utf-8") as handle:
        payload = json.load(handle)

    low = exact_rows(payload, LOW)
    high = exact_rows(payload, HIGH)
    if set(low) != set(high) or len(low) != 12:
        raise SystemExit("matched-seed contract violated")

    high_success = {seed: bool(row["reliable_exact"]) for seed, row in high.items()}
    low_success = {seed: bool(row["reliable_exact"]) for seed, row in low.items()}
    high_count = sum(high_success.values())
    low_count = sum(low_success.values())
    high_only = sum(high_success[s] and not low_success[s] for s in high_success)
    low_only = sum(low_success[s] and not high_success[s] for s in high_success)
    p_value = one_sided_mcnemar_p(high_only, low_only)

    summary = payload["summary"]
    high_exact = summary[HIGH]["exact_c4"]
    high_wrong = summary[HIGH]["wrong_v4"]
    high_gru = summary[HIGH]["gru"]

    checks = {
        "matched_seed_contract": len(low) == 12 and set(low) == set(high),
        "higher_dose_direction": high_count > low_count,
        "paired_exact_mcnemar_p_lt_0_05": p_value < ALPHA,
        "higher_dose_reliable_on_at_least_9_of_12": high_count >= 9,
        "higher_dose_beats_wrong_far": high_exact["far_pair"]["mean"] - high_wrong["far_pair"]["mean"] > 0.20,
        "higher_dose_beats_gru_far": high_exact["far_pair"]["mean"] - high_gru["far_pair"]["mean"] > 0.20,
        "structured_not_larger_than_gru": high_exact["parameter_count"] <= high_gru["parameter_count"],
    }
    verdict = {
        "checks": checks,
        "pass": all(checks.values()),
        "counts": {
            "low_successes": low_count,
            "high_successes": high_count,
            "high_only": high_only,
            "low_only": low_only,
            "matched_seeds": len(low),
        },
        "one_sided_exact_mcnemar_p": p_value,
        "alpha": ALPHA,
    }
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
