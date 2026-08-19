"""Fresh-seed replication for the frozen geometric-symbolic v2 mechanism.

This runner deliberately reuses the exact v2 model/training/evaluation code and
changes only the seed set. It exists to test a separately preregistered v3
adjudication rule without retuning the mechanism after seeing v2 results.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from statistics import mean, pstdev

V2_DIR = Path(__file__).resolve().parents[1] / "geometric_symbolic_v2"
sys.path.insert(0, str(V2_DIR))

from geometric_symbolic_v2 import MODES, train_one  # noqa: E402

import torch  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--seed-start", type=int, default=101)
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    torch.set_num_threads(1)
    device = torch.device("cpu")
    seed_values = list(range(args.seed_start, args.seed_start + args.seeds))
    rows = []

    for mode in MODES:
        for seed in seed_values:
            row = asdict(train_one(seed, mode, args.steps, device))
            rows.append(row)
            print(json.dumps(row))

    keys = (
        "train_acc",
        "ood8_acc",
        "ood16_acc",
        "ood32_acc",
        "pair16_acc",
        "pair32_acc",
        "invariant32_acc",
    )
    summary = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        summary[mode] = {}
        for key in keys:
            values = [row[key] for row in mode_rows]
            summary[mode][key] = {"mean": mean(values), "sd": pstdev(values)}

    payload = {
        "experiment": {
            "mechanism_source": "exact v2 mechanism from closed PR #142",
            "v2_head": "d49220360c8711a0cda494b809c4c2a0c081d41e",
            "fresh_seed_values": seed_values,
            "steps": args.steps,
            "scope_limit": "toy symbolic replication; not Sophontic reproduction",
        },
        "rows": rows,
        "summary": summary,
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    print("\nSUMMARY")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
