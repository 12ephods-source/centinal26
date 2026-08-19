"""Causally coupled Z2 latent-geometry reasoning test.

Successor to frozen PR #121. Unlike v1, prediction is read directly from a
structured 2-D latent subspace, so the model cannot solve the task while
completely ignoring the geometry probe.

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
        e = self.edge_emb(edge)
        d = self.dist_emb(distractor)
        return h + 0.25 * self.step(torch.cat([h, e, d], dim=-1))

    def z(self, h):
        return self.proj(h)

    def logits(self, h):
        return self.logit_scale * self.z(h)[:, 0]

    def forward(self, edges, distractors):
        h = self.start.expand(edges.shape[0], -1)
        hs = [h]
        for t in range(edges.shape[1]):
            h = self.transition(h, edges[:, t], distractors[:, t])
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
    out = z.clone()
    out[:, 0] = -out[:, 0]
    return out


def geometry_loss(model, hs, edges, distractors, mode):
    if mode == "baseline":
        return torch.tensor(0.0, device=edges.device)

    total = torch.tensor(0.0, device=edges.device)
    count = 0
    z0 = model.z(hs[0])
    anchor = torch.zeros_like(z0)
    anchor[:, 0] = 1.0
    total = total + 0.25 * F.mse_loss(z0, anchor)

    for t in range(edges.shape[1]):
        z_before = model.z(hs[t])
        z_after = model.z(hs[t + 1])
        edge = edges[:, t]

        if mode == "correct_geo":
            expected = torch.where(edge[:, None] == 0, z_before, reflect(z_before))
        else:
            expected = torch.where(edge[:, None] == 0, reflect(z_before), z_before)

        total = total + F.mse_loss(z_after, expected)
        flipped_d = 1 - distractors[:, t]
        h_cf = model.transition(hs[t], edge, flipped_d)
        z_cf = model.z(h_cf)
        total = total + 0.35 * F.mse_loss(z_cf, z_after)
        total = total + 0.05 * ((z_after.norm(dim=1) - 1.0) ** 2).mean()
        count += 1

    return total / max(count, 1)


@dataclass
class Metrics:
    seed: int
    mode: str
    train_acc: float
    ood8_acc: float
    ood16_acc: float
    ood32_acc: float
    pair16_acc: float
    pair32_acc: float
    invariant32_acc: float


def pred(logits):
    return torch.where(logits >= 0, 1.0, -1.0)


def eval_plain(model, device, length, batches=16, batch=256):
    model.eval()
    values = []
    with torch.no_grad():
        for _ in range(batches):
            edges, dist, target = make_batch(batch, length, length, device, fixed_len=length)
            logits, _ = model(edges, dist)
            values.append((pred(logits) == target).float().mean().item())
    return mean(values)


def make_pairs(batch, length, device):
    edges, dist, target = make_batch(batch, length, length, device, fixed_len=length)
    idx = torch.arange(batch, device=device)
    edge_pos = torch.randint(0, length, (batch,), device=device)
    edge_flip = edges.clone()
    edge_flip[idx, edge_pos] ^= 1
    dist_pos = torch.randint(0, length, (batch,), device=device)
    dist_flip = dist.clone()
    dist_flip[idx, dist_pos] ^= 1
    return edges, dist, target, edge_flip, -target, dist_flip


def eval_pairs(model, device, length, batches=16, batch=256):
    model.eval()
    pair_values = []
    invariant_values = []
    with torch.no_grad():
        for _ in range(batches):
            edges, dist, target, edge_flip, flipped_target, dist_flip = make_pairs(
                batch, length, device
            )
            a, _ = model(edges, dist)
            b, _ = model(edge_flip, dist)
            c, _ = model(edges, dist_flip)
            pa, pb, pc = pred(a), pred(b), pred(c)
            pair_values.append(
                ((pa == target) & (pb == flipped_target)).float().mean().item()
            )
            invariant_values.append(
                ((pa == target) & (pc == target)).float().mean().item()
            )
    return mean(pair_values), mean(invariant_values)


def train_one(seed, mode, steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    model = Reasoner().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)

    for step in range(steps):
        model.train()
        edges, dist, target = make_batch(256, 1, 4, device)
        logits, hs = model(edges, dist)
        task = F.softplus(-target * logits).mean()
        geo = geometry_loss(model, hs, edges, dist, mode)
        ramp = min(1.0, (step + 1) / 120)
        loss = task + ramp * 0.12 * geo
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

    train_acc = eval_plain(model, device, 4, batches=8)
    ood8 = eval_plain(model, device, 8)
    ood16 = eval_plain(model, device, 16)
    ood32 = eval_plain(model, device, 32)
    pair16, _ = eval_pairs(model, device, 16)
    pair32, invariant32 = eval_pairs(model, device, 32)
    return Metrics(seed, mode, train_acc, ood8, ood16, ood32, pair16, pair32, invariant32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    torch.set_num_threads(1)
    device = torch.device("cpu")
    rows = []

    for mode in MODES:
        for seed in range(args.seeds):
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
        rs = [row for row in rows if row["mode"] == mode]
        summary[mode] = {}
        for key in keys:
            vals = [row[key] for row in rs]
            summary[mode][key] = {"mean": mean(vals), "sd": pstdev(vals)}

    payload = {
        "experiment": {
            "successor_to": "PR #121 frozen FAIL/REVIEW",
            "task": "Z2 signed-edge symbolic composition with irrelevant distractors",
            "causal_coupling": "answer logit is first coordinate of constrained 2-D latent subspace",
            "train_lengths": [1, 2, 3, 4],
            "ood_lengths": [8, 16, 32],
            "conditions": list(MODES),
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
