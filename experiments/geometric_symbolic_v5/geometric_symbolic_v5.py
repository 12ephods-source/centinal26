"""Exact-operator group-specificity test for geometric reasoning.

All conditions use the same exact SO(4)-operator architecture. The experiment
asks whether imposing the *correct* C4 multiplication law improves
compositional generalization beyond no relation penalty, a generic operator-
separation penalty, or an equally structured but incorrect Klein-four (V4)
relation penalty.

This is a toy mechanistic test, not a Sophontic reproduction.
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

MODES = ("baseline", "generic", "correct_c4", "wrong_v4")
SEEDS = (30, 31, 32)
NEAR_LENGTHS = (11, 12, 13)
FAR_LENGTHS = (31, 32, 33)


class ExactOperatorReasoner(nn.Module):
    def __init__(self, dim: int = 4):
        super().__init__()
        self.raw_ops = nn.Parameter(torch.randn(4, dim, dim) * 0.15)
        self.start = nn.Parameter(torch.randn(dim) * 0.1)
        self.head = nn.Linear(dim, 4)

    def operators(self):
        skew = self.raw_ops - self.raw_ops.transpose(-1, -2)
        return torch.matrix_exp(0.35 * skew)

    def forward(self, tokens):
        ops = self.operators()
        state = self.start.expand(tokens.shape[0], -1)
        for step in range(tokens.shape[1]):
            q = ops[tokens[:, step]]
            state = torch.bmm(q, state.unsqueeze(-1)).squeeze(-1)
        return self.head(state)


def make_batch(batch, min_len, max_len, device, fixed_len=None):
    length = fixed_len if fixed_len is not None else random.randint(min_len, max_len)
    tokens = torch.randint(0, 4, (batch, length), device=device)
    target = tokens.sum(dim=1) % 4
    return tokens, target


def relation_target(left, right, law):
    if law == "c4":
        return (left + right) % 4
    if law == "v4":
        return left ^ right
    raise ValueError(law)


def relation_loss(model, law):
    ops = model.operators()
    losses = []
    for left in range(4):
        for right in range(4):
            target = relation_target(left, right, law)
            product = ops[left] @ ops[right]
            losses.append(F.mse_loss(product, ops[target]))
    return torch.stack(losses).mean()


def generic_separation_loss(model):
    ops = model.operators().flatten(1)
    ops = F.normalize(ops, dim=1)
    penalties = []
    for left in range(4):
        for right in range(left + 1, 4):
            penalties.append((ops[left] @ ops[right]).square())
    return torch.stack(penalties).mean()


def structural_penalty(model, mode):
    if mode == "baseline":
        return torch.tensor(0.0, device=model.raw_ops.device)
    if mode == "generic":
        return generic_separation_loss(model)
    if mode == "correct_c4":
        return relation_loss(model, "c4")
    if mode == "wrong_v4":
        return relation_loss(model, "v4")
    raise ValueError(mode)


@dataclass
class Metrics:
    seed: int
    mode: str
    train_acc: float
    near_acc: float
    near_pair: float
    far_acc: float
    far_pair: float
    c4_residual: float
    v4_residual: float


def accuracy(logits, target):
    return (logits.argmax(dim=1) == target).float().mean().item()


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
            canonical_logits = model(tokens)
            perturbed_logits = model(perturbed)
            canonical = canonical_logits.argmax(dim=1)
            changed = perturbed_logits.argmax(dim=1)
            accuracies.append((canonical == target).float().mean().item())
            pair_accuracies.append(
                ((canonical == target) & (changed == perturbed_target)).float().mean().item()
            )
    return mean(accuracies), mean(pair_accuracies)


def eval_lengths(model, device, lengths):
    rows = [eval_length(model, device, length) for length in lengths]
    return tuple(mean(values) for values in zip(*rows))


def train_one(seed, mode, steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    model = ExactOperatorReasoner().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)

    for step in range(steps):
        model.train()
        tokens, target = make_batch(256, 1, 4, device)
        logits = model(tokens)
        task_loss = F.cross_entropy(logits, target)
        penalty = structural_penalty(model, mode)
        ramp = min(1.0, (step + 1) / 150)
        loss = task_loss + ramp * 0.10 * penalty

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

    train_acc, _ = eval_length(model, device, 4, batches=8)
    near_acc, near_pair = eval_lengths(model, device, NEAR_LENGTHS)
    far_acc, far_pair = eval_lengths(model, device, FAR_LENGTHS)

    with torch.no_grad():
        c4_residual = relation_loss(model, "c4").item()
        v4_residual = relation_loss(model, "v4").item()

    return Metrics(
        seed=seed,
        mode=mode,
        train_acc=train_acc,
        near_acc=near_acc,
        near_pair=near_pair,
        far_acc=far_acc,
        far_pair=far_pair,
        c4_residual=c4_residual,
        v4_residual=v4_residual,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=700)
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

    metric_names = (
        "train_acc",
        "near_acc",
        "near_pair",
        "far_acc",
        "far_pair",
        "c4_residual",
        "v4_residual",
    )
    summary = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        summary[mode] = {}
        for metric in metric_names:
            values = [row[metric] for row in mode_rows]
            summary[mode][metric] = {"mean": mean(values), "sd": pstdev(values)}

    payload = {
        "experiment": {
            "successor_to": "PR #148 frozen v4 FAIL",
            "task": "C4 four-symbol composition",
            "shared_operator_manifold": "exact SO(4) transitions in every condition",
            "fresh_seeds": list(SEEDS),
            "near_lengths": list(NEAR_LENGTHS),
            "far_lengths": list(FAR_LENGTHS),
            "conditions": list(MODES),
            "correct_relation": "C4 addition modulo 4",
            "wrong_relation": "Klein-four XOR law",
            "scope_limit": "toy mechanistic test; not Sophontic reproduction",
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
