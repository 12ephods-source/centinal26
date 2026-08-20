"""Anti-aliasing symbolic geometry experiment.

The v2/v3 negative control swapped positive/negative edge semantics. On fixed
even chain lengths that swap is parity-equivalent to the correct rule. v4 uses
mixed odd/even evaluation lengths and a genuinely false active control: both
edge types are constrained to reflect the task coordinate.

This remains a toy mechanism test, not a Sophontic reproduction.
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

MODES = ("baseline", "correct_geo", "wrong_geo")
SEEDS = (20, 21, 22)
NEAR_LENGTHS = (15, 16, 17)
FAR_LENGTHS = (31, 32, 33)


class Reasoner(nn.Module):
    def __init__(self, hidden: int = 32):
        super().__init__()
        self.start = nn.Parameter(torch.zeros(hidden))
        self.edge_emb = nn.Embedding(2, hidden)
        self.dist_emb = nn.Embedding(2, hidden)
        self.step = nn.Sequential(
            nn.Linear(hidden * 3, hidden),
            nn.Tanh(),
            nn.Linear(hidden, hidden),
        )
        self.proj = nn.Linear(hidden, 2)
        self.logit_scale = nn.Parameter(torch.tensor(1.0))

    def transition(self, h, edge, distractor):
        edge_vec = self.edge_emb(edge)
        dist_vec = self.dist_emb(distractor)
        delta = self.step(torch.cat([h, edge_vec, dist_vec], dim=-1))
        return h + 0.25 * delta

    def z(self, h):
        return self.proj(h)

    def logits(self, h):
        return self.logit_scale * self.z(h)[:, 0]

    def forward(self, edges, distractors):
        h = self.start.expand(edges.shape[0], -1)
        hs = [h]
        for step in range(edges.shape[1]):
            h = self.transition(h, edges[:, step], distractors[:, step])
            hs.append(h)
        return self.logits(h), hs


def make_batch(batch, min_len, max_len, device, fixed_len=None):
    length = fixed_len if fixed_len is not None else random.randint(min_len, max_len)
    edges = torch.randint(0, 2, (batch, length), device=device)
    distractors = torch.randint(0, 2, (batch, length), device=device)
    flips = edges.sum(dim=1) % 2
    target = torch.where(flips == 0, 1.0, -1.0)
    return edges, distractors, target


def reflect(z):
    reflected = z.clone()
    reflected[:, 0] = -reflected[:, 0]
    return reflected


def geometry_loss(model, hs, edges, distractors, mode):
    if mode == "baseline":
        return torch.tensor(0.0, device=edges.device)

    total = torch.tensor(0.0, device=edges.device)
    z0 = model.z(hs[0])
    anchor = torch.zeros_like(z0)
    anchor[:, 0] = 1.0
    total = total + 0.25 * F.mse_loss(z0, anchor)

    for step in range(edges.shape[1]):
        z_before = model.z(hs[step])
        z_after = model.z(hs[step + 1])
        edge = edges[:, step]

        if mode == "correct_geo":
            expected = torch.where(edge[:, None] == 0, z_before, reflect(z_before))
        else:
            # Genuinely false active control: both symbols reflect.
            expected = reflect(z_before)

        total = total + F.mse_loss(z_after, expected)

        flipped_dist = 1 - distractors[:, step]
        h_counterfactual = model.transition(hs[step], edge, flipped_dist)
        z_counterfactual = model.z(h_counterfactual)
        total = total + 0.35 * F.mse_loss(z_counterfactual, z_after)
        total = total + 0.05 * ((z_after.norm(dim=1) - 1.0) ** 2).mean()

    return total / edges.shape[1]


@dataclass
class Metrics:
    seed: int
    mode: str
    train_acc: float
    near_acc: float
    near_pair: float
    near_invariant: float
    far_acc: float
    far_pair: float
    far_invariant: float


def prediction(logits):
    return torch.where(logits >= 0, 1.0, -1.0)


def make_pairs(batch, length, device):
    edges, distractors, target = make_batch(batch, length, length, device, fixed_len=length)
    row = torch.arange(batch, device=device)

    edge_position = torch.randint(0, length, (batch,), device=device)
    edge_flip = edges.clone()
    edge_flip[row, edge_position] ^= 1

    distractor_position = torch.randint(0, length, (batch,), device=device)
    distractor_flip = distractors.clone()
    distractor_flip[row, distractor_position] ^= 1

    return edges, distractors, target, edge_flip, -target, distractor_flip


def eval_length(model, device, length, batches=16, batch=256):
    model.eval()
    accuracies = []
    pair_accuracies = []
    invariant_accuracies = []

    with torch.no_grad():
        for _ in range(batches):
            edges, dist, target, edge_flip, flipped_target, dist_flip = make_pairs(
                batch, length, device
            )
            canonical_logits, _ = model(edges, dist)
            flipped_logits, _ = model(edge_flip, dist)
            invariant_logits, _ = model(edges, dist_flip)

            canonical = prediction(canonical_logits)
            flipped = prediction(flipped_logits)
            invariant = prediction(invariant_logits)

            accuracies.append((canonical == target).float().mean().item())
            pair_accuracies.append(
                ((canonical == target) & (flipped == flipped_target)).float().mean().item()
            )
            invariant_accuracies.append(
                ((canonical == target) & (invariant == target)).float().mean().item()
            )

    return mean(accuracies), mean(pair_accuracies), mean(invariant_accuracies)


def eval_lengths(model, device, lengths):
    rows = [eval_length(model, device, length) for length in lengths]
    return tuple(mean(values) for values in zip(*rows))


def train_one(seed, mode, steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    model = Reasoner().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)

    for step in range(steps):
        model.train()
        edges, distractors, target = make_batch(256, 1, 4, device)
        logits, hs = model(edges, distractors)
        task_loss = F.softplus(-target * logits).mean()
        geo_loss = geometry_loss(model, hs, edges, distractors, mode)
        ramp = min(1.0, (step + 1) / 120)
        loss = task_loss + ramp * 0.12 * geo_loss

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

    train_acc, _, _ = eval_length(model, device, 4, batches=8)
    near_acc, near_pair, near_invariant = eval_lengths(model, device, NEAR_LENGTHS)
    far_acc, far_pair, far_invariant = eval_lengths(model, device, FAR_LENGTHS)

    return Metrics(
        seed=seed,
        mode=mode,
        train_acc=train_acc,
        near_acc=near_acc,
        near_pair=near_pair,
        near_invariant=near_invariant,
        far_acc=far_acc,
        far_pair=far_pair,
        far_invariant=far_invariant,
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

    metric_names = (
        "train_acc",
        "near_acc",
        "near_pair",
        "near_invariant",
        "far_acc",
        "far_pair",
        "far_invariant",
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
            "successor_to": "PR #147 frozen v3 FAIL",
            "fresh_seeds": list(SEEDS),
            "task": "Z2 signed-edge composition with irrelevant distractors",
            "near_lengths": list(NEAR_LENGTHS),
            "far_lengths": list(FAR_LENGTHS),
            "wrong_control": "both edge types constrained to reflect",
            "scope_limit": "toy symbolic mechanism; not Sophontic reproduction",
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
