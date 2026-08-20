"""Fresh-seed continuous-metric successor to geometric symbolic v2.

v2 correctly remained FAIL because its bounded wrong-geometry pair-accuracy
criterion hit a floor. v3 does not edit v2. It evaluates the same causal Z2
latent construction on fresh seeds and adds an unbounded held-out logistic-loss
negative control at chain length 64.

This remains a toy symbolic mechanism test, not a Sophontic reproduction.
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
DEFAULT_SEEDS = (10, 11, 12)


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
        update = self.step(torch.cat([h, edge_vec, dist_vec], dim=-1))
        return h + 0.25 * update

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
            expected = torch.where(edge[:, None] == 0, reflect(z_before), z_before)

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
    ood32_acc: float
    ood64_acc: float
    ood64_logistic_loss: float
    pair32_acc: float
    pair64_acc: float
    invariant64_acc: float
    pair64_margin: float


def prediction(logits):
    return torch.where(logits >= 0, 1.0, -1.0)


def eval_plain(model, device, length, batches=20, batch=256):
    model.eval()
    accuracies = []
    losses = []
    with torch.no_grad():
        for _ in range(batches):
            edges, distractors, target = make_batch(
                batch, length, length, device, fixed_len=length
            )
            logits, _ = model(edges, distractors)
            accuracies.append((prediction(logits) == target).float().mean().item())
            losses.append(F.softplus(-target * logits).mean().item())
    return mean(accuracies), mean(losses)


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


def eval_pairs(model, device, length, batches=20, batch=256):
    model.eval()
    pair_acc = []
    invariant_acc = []
    pair_margin = []

    with torch.no_grad():
        for _ in range(batches):
            edges, dist, target, edge_flip, flipped_target, dist_flip = make_pairs(
                batch, length, device
            )
            canonical_logits, _ = model(edges, dist)
            flipped_logits, _ = model(edge_flip, dist)
            invariant_logits, _ = model(edges, dist_flip)

            canonical_pred = prediction(canonical_logits)
            flipped_pred = prediction(flipped_logits)
            invariant_pred = prediction(invariant_logits)

            pair_acc.append(
                (
                    (canonical_pred == target)
                    & (flipped_pred == flipped_target)
                )
                .float()
                .mean()
                .item()
            )
            invariant_acc.append(
                (
                    (canonical_pred == target)
                    & (invariant_pred == target)
                )
                .float()
                .mean()
                .item()
            )

            canonical_margin = target * canonical_logits
            flipped_margin = flipped_target * flipped_logits
            pair_margin.append(torch.minimum(canonical_margin, flipped_margin).mean().item())

    return mean(pair_acc), mean(invariant_acc), mean(pair_margin)


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

    train_acc, _ = eval_plain(model, device, 4, batches=10)
    ood32_acc, _ = eval_plain(model, device, 32)
    ood64_acc, ood64_loss = eval_plain(model, device, 64)
    pair32_acc, _, _ = eval_pairs(model, device, 32)
    pair64_acc, invariant64_acc, pair64_margin = eval_pairs(model, device, 64)

    return Metrics(
        seed=seed,
        mode=mode,
        train_acc=train_acc,
        ood32_acc=ood32_acc,
        ood64_acc=ood64_acc,
        ood64_logistic_loss=ood64_loss,
        pair32_acc=pair32_acc,
        pair64_acc=pair64_acc,
        invariant64_acc=invariant64_acc,
        pair64_margin=pair64_margin,
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
        for seed in DEFAULT_SEEDS:
            row = asdict(train_one(seed, mode, args.steps, device))
            rows.append(row)
            print(json.dumps(row))

    metrics = (
        "train_acc",
        "ood32_acc",
        "ood64_acc",
        "ood64_logistic_loss",
        "pair32_acc",
        "pair64_acc",
        "invariant64_acc",
        "pair64_margin",
    )
    summary = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        summary[mode] = {}
        for metric in metrics:
            values = [row[metric] for row in mode_rows]
            summary[mode][metric] = {"mean": mean(values), "sd": pstdev(values)}

    payload = {
        "experiment": {
            "successor_to": "PR #142 frozen v2 gate FAIL",
            "fresh_seeds": list(DEFAULT_SEEDS),
            "task": "Z2 signed-edge composition with irrelevant distractors",
            "train_lengths": [1, 2, 3, 4],
            "ood_lengths": [32, 64],
            "new_negative_control_metric": "OOD64 logistic loss",
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
