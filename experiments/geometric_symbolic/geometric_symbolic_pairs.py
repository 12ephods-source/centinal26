"""Symbolic canonical/perturbed-pair test for geometry-constrained reasoning.

Task:
- A chain contains logical edge signs (+1 = preserve, -1 = negate) plus irrelevant distractors.
- The target is the product of logical edge signs (a Z2 composition law).
- A canonical/perturbed pair flips exactly one load-bearing logical edge, so the target must flip.
- An invariant pair flips only a distractor, so the target must stay fixed.

All three conditions use the same architecture and execute both candidate geometry losses:
- baseline: task loss only (geometry losses multiplied by zero)
- correct_geo: encourages + as identity and - as sign reflection/involution
- wrong_geo: deliberately swaps those semantics

This is a toy symbolic mechanism test, not a reproduction of Sophontic.
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


class SymbolicReasoner(nn.Module):
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
        self.probe = nn.Linear(hidden, 1, bias=False)
        self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.Tanh(), nn.Linear(hidden, 1))

    def transition(self, h, edge_idx, dist_idx):
        e = self.edge_emb(edge_idx)
        d = self.dist_emb(dist_idx)
        return h + 0.25 * self.step(torch.cat([h, e, d], dim=-1))

    def forward(self, edge_idx, dist_idx):
        h = self.start.expand(edge_idx.shape[0], -1)
        hs = [h]
        for t in range(edge_idx.shape[1]):
            h = self.transition(h, edge_idx[:, t], dist_idx[:, t])
            hs.append(h)
        return self.head(h).squeeze(-1), hs


def edge_idx_to_sign(edge_idx):
    return torch.where(edge_idx == 1, -torch.ones_like(edge_idx), torch.ones_like(edge_idx))


def make_batch(batch, min_len, max_len, device, fixed_len=None):
    length = fixed_len if fixed_len is not None else random.randint(min_len, max_len)
    edge = torch.randint(0, 2, (batch, length), device=device)
    distractor = torch.randint(0, 2, (batch, length), device=device)
    sign = edge_idx_to_sign(edge)
    target = sign.prod(dim=1).float()
    return edge, distractor, target


def make_pairs(batch, length, device):
    edge, distractor, target = make_batch(batch, length, length, device, fixed_len=length)

    positions = torch.randint(0, length, (batch,), device=device)
    edge_flip = edge.clone()
    edge_flip[torch.arange(batch, device=device), positions] ^= 1
    target_flip = -target

    dist_flip = distractor.clone()
    dist_positions = torch.randint(0, length, (batch,), device=device)
    dist_flip[torch.arange(batch, device=device), dist_positions] ^= 1

    return edge, distractor, target, edge_flip, target_flip, dist_flip


def geometry_losses(model, hs, edge_idx, dist_idx):
    compact = torch.tensor(0.0, device=edge_idx.device)
    correct = torch.tensor(0.0, device=edge_idx.device)
    wrong = torch.tensor(0.0, device=edge_idx.device)

    for t in range(edge_idx.shape[1]):
        z0 = model.probe(hs[t]).squeeze(-1)
        z1 = model.probe(hs[t + 1]).squeeze(-1)
        edge_t = edge_idx[:, t]

        pos = edge_t == 0
        neg = edge_t == 1

        if pos.any():
            correct = correct + F.mse_loss(z1[pos], z0[pos])
            wrong = wrong + F.mse_loss(z1[pos], -z0[pos])

        if neg.any():
            correct = correct + F.mse_loss(z1[neg], -z0[neg])
            wrong = wrong + F.mse_loss(z1[neg], z0[neg])

        compact = compact + 1e-4 * (z1.square().mean() + z0.square().mean())

    h = hs[0]
    zeros = torch.zeros(h.shape[0], device=h.device, dtype=torch.long)
    ones = torch.ones(h.shape[0], device=h.device, dtype=torch.long)
    dist0 = dist_idx[:, 0]

    h_pos = model.transition(h, zeros, dist0)
    h_neg = model.transition(h, ones, dist0)
    h_neg2 = model.transition(h_neg, ones, dist0)

    z = model.probe(h).squeeze(-1)
    z_pos = model.probe(h_pos).squeeze(-1)
    z_neg = model.probe(h_neg).squeeze(-1)
    z_neg2 = model.probe(h_neg2).squeeze(-1)

    correct = correct + F.mse_loss(z_pos, z) + F.mse_loss(z_neg, -z)
    correct = correct + 0.5 * F.mse_loss(z_neg2, z)

    wrong = wrong + F.mse_loss(z_pos, -z) + F.mse_loss(z_neg, z)
    wrong = wrong + 0.5 * F.mse_loss(z_neg2, z_neg)

    return correct + compact, wrong + compact


@dataclass
class Metrics:
    seed: int
    mode: str
    train_acc: float
    ood8_acc: float
    ood16_acc: float
    pair8_acc: float
    pair16_acc: float
    invariant16_acc: float


def accuracy_from_logits(logits, target):
    pred = torch.where(logits >= 0, torch.ones_like(logits), -torch.ones_like(logits))
    return (pred == target).float().mean().item()


def eval_plain(model, device, length, batches=20, batch=256):
    model.eval()
    accs = []
    with torch.no_grad():
        for _ in range(batches):
            edge, dist, target = make_batch(batch, length, length, device, fixed_len=length)
            logits, _ = model(edge, dist)
            accs.append(accuracy_from_logits(logits, target))
    return mean(accs)


def eval_pairs(model, device, length, batches=20, batch=256):
    model.eval()
    pair_accs = []
    invariant_accs = []
    with torch.no_grad():
        for _ in range(batches):
            edge, dist, target, edge_flip, target_flip, dist_flip = make_pairs(
                batch, length, device
            )
            a, _ = model(edge, dist)
            b, _ = model(edge_flip, dist)
            c, _ = model(edge, dist_flip)

            pa = torch.where(a >= 0, torch.ones_like(a), -torch.ones_like(a))
            pb = torch.where(b >= 0, torch.ones_like(b), -torch.ones_like(b))
            pc = torch.where(c >= 0, torch.ones_like(c), -torch.ones_like(c))

            pair_accs.append(((pa == target) & (pb == target_flip)).float().mean().item())
            invariant_accs.append(((pa == target) & (pc == target)).float().mean().item())
    return mean(pair_accs), mean(invariant_accs)


def train_one(seed, mode, steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    model = SymbolicReasoner().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)

    for step in range(steps):
        model.train()
        edge, dist, target = make_batch(256, 1, 4, device)
        logits, hs = model(edge, dist)
        task = F.softplus(-target * logits).mean()

        correct_geo, wrong_geo = geometry_losses(model, hs, edge, dist)
        ramp = min(1.0, (step + 1) / 150)

        if mode == "baseline":
            loss = task + 0.0 * correct_geo + 0.0 * wrong_geo
        elif mode == "correct_geo":
            loss = task + ramp * 0.08 * correct_geo + 0.0 * wrong_geo
        else:
            loss = task + 0.0 * correct_geo + ramp * 0.08 * wrong_geo

        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

    train_acc = eval_plain(model, device, 4, batches=10)
    ood8 = eval_plain(model, device, 8)
    ood16 = eval_plain(model, device, 16)
    pair8, _ = eval_pairs(model, device, 8)
    pair16, invariant16 = eval_pairs(model, device, 16)

    return Metrics(seed, mode, train_acc, ood8, ood16, pair8, pair16, invariant16)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--out", default="symbolic_results.json")
    args = parser.parse_args()

    torch.set_num_threads(1)
    device = torch.device("cpu")

    rows = []
    for mode in MODES:
        for seed in range(args.seeds):
            metrics = train_one(seed, mode, args.steps, device)
            row = asdict(metrics)
            rows.append(row)
            print(json.dumps(row))

    summary = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        summary[mode] = {}
        for key in (
            "train_acc",
            "ood8_acc",
            "ood16_acc",
            "pair8_acc",
            "pair16_acc",
            "invariant16_acc",
        ):
            values = [row[key] for row in mode_rows]
            summary[mode][key] = {"mean": mean(values), "sd": pstdev(values)}

    result = {
        "experiment": {
            "task": "signed implication-chain composition with irrelevant distractors",
            "train_chain_lengths": [1, 2, 3, 4],
            "ood_chain_lengths": [8, 16],
            "pair_definition": "flip one load-bearing edge => target sign flips",
            "invariant_pair_definition": "flip one distractor => target unchanged",
            "same_architecture": True,
            "same_training_steps": True,
            "same_geometry_loss_computation": True,
            "interpretation_limit": (
                "toy symbolic test; not an LLM benchmark or Sophontic reproduction"
            ),
        },
        "rows": rows,
        "summary": summary,
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    print("\nSUMMARY")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
