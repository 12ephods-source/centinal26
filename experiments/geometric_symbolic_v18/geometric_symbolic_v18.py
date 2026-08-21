"""v18 confirmatory replication of the 10% singleton-anchor mechanism.

This gate follows the failed v17 matched-dose boundary test. It does not search
another dose. Instead it freezes the previously successful 10% anchor rate and
asks whether the narrow exact-C4 mechanism replicates across 12 fresh seeds with
matched wrong-V4 and GRU controls under the same 700-step budget and OOD tests.
"""

from __future__ import annotations

import argparse
import importlib
import json
import pathlib
import sys
from dataclasses import asdict
from statistics import mean, pstdev

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

v11 = importlib.import_module("experiments.geometric_symbolic_v11.geometric_symbolic_v11")

ANCHOR_RATE = 0.10
SEEDS = tuple(range(170, 182))


def reliable_exact(row):
    return bool(
        row["mode"] == "exact_c4"
        and row["singleton_acc"] > 0.98
        and row["token_grounding_acc"] is not None
        and row["token_grounding_acc"] > 0.98
        and row["train_pair"] > 0.95
        and row["near_pair"] > 0.95
        and row["far_pair"] > 0.90
    )


def summarize(rows):
    summary = {}
    for mode in v11.MODES:
        mode_rows = [r for r in rows if r["mode"] == mode]
        entry = {"parameter_count": mode_rows[0]["parameter_count"]}
        for metric in (
            "singleton_acc",
            "train_pair",
            "near_acc",
            "near_pair",
            "far_acc",
            "far_pair",
        ):
            values = [r[metric] for r in mode_rows]
            entry[metric] = {"mean": mean(values), "sd": pstdev(values)}
        grounds = [r["token_grounding_acc"] for r in mode_rows if r["token_grounding_acc"] is not None]
        if grounds:
            entry["token_grounding_acc"] = {"mean": mean(grounds), "sd": pstdev(grounds)}
        summary[mode] = entry
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=700)
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    v11.torch.set_num_threads(1)
    v11.ANCHOR_RATE = ANCHOR_RATE
    device = v11.torch.device("cpu")
    rows = []

    for mode in v11.MODES:
        for seed in SEEDS:
            row = asdict(v11.train_one(seed, mode, args.steps, device))
            row["anchor_rate"] = ANCHOR_RATE
            row["reliable_exact"] = reliable_exact(row)
            rows.append(row)
            print(json.dumps(row, sort_keys=True))

    payload = {
        "experiment": {
            "successor_to": "PR #169 v17 matched-dose scientific FAIL",
            "claim": "the frozen 10% singleton-anchor exact-C4 mechanism replicates across 12 fresh seeds",
            "anchor_rate": ANCHOR_RATE,
            "fresh_seeds": list(SEEDS),
            "steps": args.steps,
            "near_lengths": list(v11.NEAR_LENGTHS),
            "far_lengths": list(v11.FAR_LENGTHS),
            "controls": list(v11.MODES),
            "supervision": "sequence labels only; no separate encoder/token-label loss",
            "counterfactual_loss": "same output-level +1 relation for all model families",
            "scope_limit": "synthetic surfaces only; not Sophontic or natural-language reasoning",
        },
        "rows": rows,
        "summary": summarize(rows),
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    print("\nSUMMARY")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
