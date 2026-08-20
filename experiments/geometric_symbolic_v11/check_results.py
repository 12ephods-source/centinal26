from __future__ import annotations

import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results")
    args = parser.parse_args()

    with open(args.results, encoding="utf-8") as handle:
        payload = json.load(handle)

    summary = payload["summary"]
    exact = summary["exact_c4"]
    wrong = summary["wrong_v4"]
    gru = summary["gru"]

    checks = {
        "singleton_grounding": exact["singleton_acc"]["mean"] > 0.98,
        "latent_grounding": exact["token_grounding_acc"]["mean"] > 0.98,
        "structured_fits_paired_training": exact["train_pair"]["mean"] > 0.95,
        "structured_near_pair": exact["near_pair"]["mean"] > 0.95,
        "structured_far_pair": exact["far_pair"]["mean"] > 0.90,
        "structured_beats_wrong_far": (
            exact["far_pair"]["mean"] - wrong["far_pair"]["mean"] > 0.20
        ),
        "structured_beats_gru_far": (
            exact["far_pair"]["mean"] - gru["far_pair"]["mean"] > 0.20
        ),
        "structured_not_larger_than_gru": exact["parameter_count"] <= gru["parameter_count"],
    }
    verdict = {"checks": checks, "pass": all(checks.values())}
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
