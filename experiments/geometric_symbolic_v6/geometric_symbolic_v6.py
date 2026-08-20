"""Exact-algebra reference test for compositional geometric reasoning.

The group law is enforced structurally rather than with a soft penalty.
All modes share one parameterized model shell. Fixed-operator modes learn a
latent basis U and conjugate a fixed orthogonal operator family by U. The
independent baseline instead learns four unrelated SO(4) operators.

A PASS would show that an explicit correct algebraic inductive bias is useful
for this toy task; it would not show that a neural network discovered the
algebra or reproduce Sophontic.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from statistics import mean, pstdev

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

MODES = ("exact_c4", "wrong_v4", "generic_fixed", "independent_so4")
SEEDS = (40, 41, 42)
NEAR_LENGTHS = (11, 12, 13)
FAR_LENGTHS = (61, 62, 63)


def permutation_matrix(mapping):
    matrix = torch.zeros(4, 4)
    for source, target in enumerate(mapping):
        matrix[target, source] = 1.0
    return matrix


def c4_operators():
    operators = []
    for shift in range(4):
        mapping = [(value + shift) % 4 for value in range(4)]
        operators.append(permutation_matrix(mapping))
    return torch.stack(operators)


def v4_operators():
    operators = []
    for element in range(4):
        mapping = [value ^ element for value in range(4)]
        operators.append(permutation_matrix(mapping))
    return torch.stack(operators)


def generic_operators():
    mappings = (
        (0, 1, 2, 3),
        (1, 0, 2, 3),
        (0, 2, 1, 3),
        (0, 1, 3, 2),
    )
    return torch.stack([permutation_matrix(mapping) for mapping in mappings])


class Reasoner(nn.Module):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.raw_basis = nn.Parameter(torch.randn(4, 4) * 0.15)
        self.raw_independent = nn.Parameter(torch.randn(4, 4, 4) * 0.15)
        self.start = nn.Parameter(torch.randn(4) * 0.1)
        self.head = nn.Linear(4, 4)

        self.register_buffer("c4_fixed", c4_operators())
        self.register_buffer("v4_fixed", v4_operators())
        self.register_buffer("generic_fixed", generic_operators())

    def basis(self):
        skew = self.raw_basis - self.raw_basis.transpose(-1, -2)
        return torch.matrix_exp(0.35 * skew)

    def operators(self):
        if self.mode == "independent_so4":
            skew = self.raw_independent - self.raw_independent.transpose(-1, -2)
            return torch.matrix_exp(0.35 * skew)

        if self.mode == "exact_c4":
            fixed = self.c4_fixed
        elif self.mode == "wrong_v4":
            fixed = self.v4_fixed
        elif self.mode == "generic_fixed":
            fixed = self.generic_fixed
        else:
            raise ValueError(self.mode)

        basis = self.basis()
        return basis.unsqueeze(0) @ fixed @ basis.transpose(-1, -2).unsqueeze(0)

    def forward(self, tokens):
        operators = self.operators()
        state = self.start.expand(tokens.shape[0], -1)
        for step in range(tokens.shape[1]):
            operator = operators[tokens[:, step]]
            state = torch.bmm(operator, state.unsqueeze(-1)).squeeze(-1)
        return self.head(state)


def make_batch(batch, min_len, max_len, device, fixed_len=None):
    length = fixed_len if fixed_len is not None else random.randint(min_len, max_len)
    tokens = torch.randint(0, 4, (batch, length), device=device)
    target = tokens.sum(dim=1) % 4
    return tokens, target


@dataclass
class Metrics:
    seed: int
    mode: str
    train_acc: float
    near_acc: float
    near_pair: float
    far_acc: float
    far_pair: float


def make_pairs(batch, length, device):
    tokens, target = make_batch(batch, length, length, device, fixed_len=length)
    row = torch.arange(batch, device=device)
    position = torch.randint(0, length, (batch,), device=device)
    perturbed = tokens.clone()
    perturbed[row, position] = (perturbed[row, position] + 1) % 4
    perturbed_target = (target + 1) % 4
    return tokens, target, perturbed, perturbed_target


def eval_length(model, device, length, batches=16, batch=256):
    model.eval()
    accuracies = []
    pair_accuracies = []
    with torch.no_grad():
        for _ in range(batches):
            tokens, target, perturbed, perturbed_target = make_pairs(batch, length, device)
            canonical = model(tokens).argmax(dim=1)
            changed = model(perturbed).argmax(dim=1)
            accuracies.append((canonical == target).float().mean().item())
            pair_accuracies.append(
                ((canonical == target) & (changed == perturbed_target)).float().mean().item()
            )
    return mean(accuracies), mean(pair_accuracies)


def eval_lengths(model, device, lengths):
    results = [eval_length(model, device, length) for length in lengths]
    return tuple(mean(values) for values in zip(*results))


def train_one(seed, mode, steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    model = Reasoner(mode).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)

    for _ in range(steps):
        model.train()
        tokens, target = make_batch(256, 1, 4, device)
        logits = model(tokens)
        loss = F.cross_entropy(logits, target)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

    train_acc, _ = eval_length(model, device, 4, batches=8)
    near_acc, near_pair = eval_lengths(model, device, NEAR_LENGTHS)
    far_acc, far_pair = eval_lengths(model, device, FAR_LENGTHS)

    return Metrics(
        seed=seed,
        mode=mode,
        train_acc=train_acc,
        near_acc=near_acc,
        near_pair=near_pair,
        far_acc=far_acc,
        far_pair=far_pair,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    torch.set_num_threads(1)
    device = torch.device("cpu")
    rows = []

    for mode in MODES:
        for seed in SEEDS:
            row = asdict(train_one(seed, mode, args.steps, device))
            rows.append(row)
            print(json.dumps(row))

    metrics = ("train_acc", "near_acc", "near_pair", "far_acc", "far_pair")
    summary = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        summary[mode] = {}
        for metric in metrics:
            values = [row[metric] for row in mode_rows]
            summary[mode][metric] = {"mean": mean(values), "sd": pstdev(values)}

    payload = {
        "experiment": {
            "successor_to": "PR #150 frozen v5 FAIL",
            "task": "C4 four-symbol composition",
            "exact_c4": "C4 regular representation conjugated by learned SO(4) basis",
            "wrong_v4": "V4 regular representation conjugated by learned SO(4) basis",
            "generic_fixed": "non-closed fixed orthogonal permutations in learned basis",
            "independent_so4": "four unrelated learned SO(4) operators",
            "fresh_seeds": list(SEEDS),
            "near_lengths": list(NEAR_LENGTHS),
            "far_lengths": list(FAR_LENGTHS),
            "scope_limit": "explicit inductive-bias reference; not learned-algebra evidence",
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
