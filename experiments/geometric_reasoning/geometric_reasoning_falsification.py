"""Toy falsification test for geometry-constrained latent reasoning.

Same recurrent architecture is trained under three conditions:
  baseline       : task loss only
  correct_geo    : task + correct latent translation geometry constraints
  wrong_geo      : task + deliberately incorrect geometry constraints

Training uses short operation chains; evaluation uses much longer unseen chains.
This does NOT reproduce Sophontic. It tests one concrete mechanism reconstructed
from its public claims: explicitly regularizing reusable latent operations.
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

OPS = torch.tensor([[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0]])  # R,L,U,D
OP_NAMES = ["R", "L", "U", "D"]


class Reasoner(nn.Module):
    def __init__(self, hidden=24):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(2, hidden), nn.Tanh(), nn.Linear(hidden, hidden))
        self.op = nn.Embedding(4, hidden)
        self.step = nn.Sequential(
            nn.Linear(hidden * 2, hidden), nn.Tanh(), nn.Linear(hidden, hidden)
        )
        self.dec = nn.Sequential(nn.Linear(hidden, hidden), nn.Tanh(), nn.Linear(hidden, 2))

    def transition(self, h, op):
        e = self.op(op)
        return h + 0.25 * self.step(torch.cat([h, e], dim=-1))

    def forward(self, x0, ops):
        h = self.enc(x0)
        hs = [h]
        for t in range(ops.shape[1]):
            h = self.transition(h, ops[:, t])
            hs.append(h)
        return self.dec(h), hs


def make_batch(batch, min_len, max_len, device, fixed_len=None):
    length = fixed_len if fixed_len is not None else random.randint(min_len, max_len)
    x0 = torch.randint(-4, 5, (batch, 2), device=device).float()
    opseq = torch.randint(0, 4, (batch, length), device=device)
    delta = OPS.to(device)[opseq].sum(dim=1)
    y = x0 + delta
    return x0, opseq, y


def geo_loss(model, hs, opseq, mode):
    # Transition deltas observed on the actual reasoning trajectory.
    deltas = []
    labels = []
    for t in range(opseq.shape[1]):
        deltas.append(hs[t + 1] - hs[t])
        labels.append(opseq[:, t])
    deltas_all = torch.cat(deltas, dim=0)
    ops_all = torch.cat(labels, dim=0)
    means = []
    compact = torch.tensor(0.0, device=deltas_all.device)
    for k in range(4):
        delta_k = deltas_all[ops_all == k]
        if len(delta_k) == 0:
            mu = torch.zeros(deltas_all.shape[1], device=deltas_all.device)
        else:
            mu = delta_k.mean(0)
            compact = compact + ((delta_k - mu) ** 2).mean()
        means.append(mu)
    m_r, m_l, m_u, m_d = means
    # Correct Euclidean translation algebra vs deliberately wrong pairing.
    if mode == "correct_geo":
        inv = ((m_r + m_l) ** 2).mean() + ((m_u + m_d) ** 2).mean()
        axis = (F.cosine_similarity(m_r[None], m_u[None]) ** 2).mean()
    elif mode == "wrong_geo":
        # Intentionally assert R and U are inverses, L and D are inverses,
        # and R should be parallel to U: structurally false for this task.
        inv = ((m_r + m_u) ** 2).mean() + ((m_l + m_d) ** 2).mean()
        axis = (1 - F.cosine_similarity(m_r[None], m_u[None])) ** 2
    else:
        return torch.tensor(0.0, device=deltas_all.device)
    return compact + 0.5 * inv + 0.15 * axis


def cycle_loss(model, h, mode, n=96):
    idx = torch.randperm(h.shape[0], device=h.device)[: min(n, h.shape[0])]
    z = h[idx]
    if mode == "correct_geo":
        pairs = [(0, 1), (1, 0), (2, 3), (3, 2)]
    else:
        pairs = [(0, 2), (2, 0), (1, 3), (3, 1)]
    total = 0.0
    for a, b in pairs:
        op_a = torch.full((len(z),), a, device=z.device, dtype=torch.long)
        op_b = torch.full((len(z),), b, device=z.device, dtype=torch.long)
        z2 = model.transition(model.transition(z, op_a), op_b)
        total = total + ((z2 - z) ** 2).mean()
    return total / len(pairs)


@dataclass
class Metrics:
    seed: int
    mode: str
    train_mse: float
    ood8_mse: float
    ood16_mse: float
    ood16_mae: float
    exact16: float
    delta_cv: float


def eval_model(model, device, length, batches=20, batch=256):
    model.eval()
    mses = []
    maes = []
    exact = []
    with torch.no_grad():
        for _ in range(batches):
            x, ops, y = make_batch(batch, length, length, device, fixed_len=length)
            prediction, _ = model(x, ops)
            error = prediction - y
            mses.append((error**2).mean().item())
            maes.append(error.abs().mean().item())
            exact.append((error.abs() < 0.5).all(dim=1).float().mean().item())
    return mean(mses), mean(maes), mean(exact)


def delta_cv(model, device):
    model.eval()
    cvs = []
    with torch.no_grad():
        x = torch.randint(-6, 7, (2048, 2), device=device).float()
        h = model.enc(x)
        for k in range(4):
            op = torch.full((len(x),), k, device=device, dtype=torch.long)
            delta = model.transition(h, op) - h
            # Coefficient of variation of transition magnitude around mean vector.
            mu = delta.mean(0)
            rms = ((delta - mu) ** 2).sum(1).sqrt().mean()
            denom = mu.norm() + 1e-8
            cvs.append((rms / denom).item())
    return mean(cvs)


def train_one(seed, mode, steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    model = Reasoner().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    for step in range(steps):
        model.train()
        x, ops, y = make_batch(192, 1, 3, device)
        prediction, hs = model(x, ops)
        task = F.mse_loss(prediction, y)
        loss = task
        if mode != "baseline":
            geometry = geo_loss(model, hs, ops, mode)
            cycle = cycle_loss(model, hs[0], mode)
            # Ramp regularization after basic task grounding.
            weight = min(1.0, (step + 1) / 150)
            loss = task + weight * (0.22 * geometry + 0.12 * cycle)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
    train_mse, _, _ = eval_model(model, device, 3, batches=10)
    ood8_mse, _, _ = eval_model(model, device, 8)
    ood16_mse, ood16_mae, exact16 = eval_model(model, device, 16)
    return Metrics(
        seed,
        mode,
        train_mse,
        ood8_mse,
        ood16_mse,
        ood16_mae,
        exact16,
        delta_cv(model, device),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=700)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--out", default="geometric_reasoning_results.json")
    args = parser.parse_args()
    torch.set_num_threads(1)
    device = torch.device("cpu")
    rows = []
    for mode in ["baseline", "correct_geo", "wrong_geo"]:
        for seed in range(args.seeds):
            metrics = train_one(seed, mode, args.steps, device)
            rows.append(asdict(metrics))
            print(json.dumps(asdict(metrics)))
    summary = {}
    for mode in ["baseline", "correct_geo", "wrong_geo"]:
        mode_rows = [row for row in rows if row["mode"] == mode]
        summary[mode] = {}
        for key in ["train_mse", "ood8_mse", "ood16_mse", "ood16_mae", "exact16", "delta_cv"]:
            values = [row[key] for row in mode_rows]
            summary[mode][key] = {"mean": mean(values), "sd": pstdev(values)}
    result = {
        "experiment": {
            "task": "2D translation composition; train chain lengths 1-3, OOD test 8 and 16",
            "same_architecture": True,
            "conditions": [
                "baseline task loss",
                "correct latent geometry regularization",
                "deliberately wrong geometry regularization",
            ],
            "interpretation_limit": (
                "toy mechanistic test; not an LLM benchmark and not a reproduction of Sophontic"
            ),
        },
        "rows": rows,
        "summary": summary,
    }
    with open(args.out, "w", encoding="utf-8") as file_handle:
        json.dump(result, file_handle, indent=2)
    print("\nSUMMARY")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
