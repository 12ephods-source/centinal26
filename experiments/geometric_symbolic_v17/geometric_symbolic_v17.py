"""v17 matched dose-replication test for the singleton-anchor boundary.

Runs the frozen v11 mechanism at 6.25% and 6.875% singleton-anchor dose on the
same fresh seeds. All three model families are retained at each dose. The
primary claim is paired: does 6.875% produce higher per-seed reliable grounding
and composition than 6.25%, rather than merely winning a three-seed midpoint
search?
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

DOSES = (0.0625, 0.06875)
SEEDS = tuple(range(150, 162))


def summarize(rows):
    summary = {}
    for dose in DOSES:
        dose_key = f"{dose:.5f}"
        summary[dose_key] = {}
        for mode in v11.MODES:
            mode_rows = [r for r in rows if r["dose"] == dose and r["mode"] == mode]
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
            summary[dose_key][mode] = entry
    return summary


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=700)
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    v11.torch.set_num_threads(1)
    device = v11.torch.device("cpu")
    rows = []
    for dose in DOSES:
        v11.ANCHOR_RATE = dose
        for mode in v11.MODES:
            for seed in SEEDS:
                row = asdict(v11.train_one(seed, mode, args.steps, device))
                row["dose"] = dose
                row["reliable_exact"] = reliable_exact(row)
                rows.append(row)
                print(json.dumps(row, sort_keys=True))

    payload = {
        "experiment": {
            "claim": "6.875% singleton anchors improve reliable exact-C4 grounding/composition over 6.25% on matched fresh seeds",
            "doses": list(DOSES),
            "fresh_matched_seeds": list(SEEDS),
            "steps": args.steps,
            "near_lengths": list(v11.NEAR_LENGTHS),
            "far_lengths": list(v11.FAR_LENGTHS),
            "supervision": "sequence labels only; no separate encoder/token-label loss",
            "controls": list(v11.MODES),
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
