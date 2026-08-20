"""Minimal sequence-level anchor test for neural grounding into an exact latent algebra.

Successor to v10. v10 showed that paired counterfactual sequence supervision can
produce a perfect exact-C4 solution in one seed but does not reliably identify
that solution across seeds. v11 adds a preregistered 10% rate of length-one
sequence examples to every model family. These are still ordinary sequence-level
labels; no encoder/token latent label is exposed through a separate objective.

The intervention tests a narrow question: is a small amount of direct
sequence-level grounding sufficient to make the exact algebra reliably usable,
while an identically grounded but wrong algebra and an unconstrained GRU remain
matched controls?
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

MODES = ("exact_c4", "wrong_v4", "gru")
SEEDS = (90, 91, 92)
NEAR_LENGTHS = (11, 12, 13)
FAR_LENGTHS = (61, 62, 63)
INPUT_DIM = 12
NOISE_STD = 0.12
ANCHOR_RATE = 0.10


def make_prototypes(seed, device):
    generator = torch.Generator(device=device)
    generator.manual_seed(seed + 2000)
    raw = torch.randn(4, INPUT_DIM, generator=generator, device=device)
    return F.normalize(raw, dim=1) * 3.0


def sample_surface(elements, prototypes):
    return prototypes[elements] + NOISE_STD * torch.randn(
        *elements.shape, INPUT_DIM, device=elements.device
    )


def target_c4(elements):
    return elements.sum(dim=1) % 4


def compose_distribution(state, token_dist, law):
    result = torch.zeros_like(state)
    for left in range(4):
        for right in range(4):
            target = (left + right) % 4 if law == "c4" else left ^ right
            result[:, target] = result[:, target] + state[:, left] * token_dist[:, right]
    return result


class StructuredReasoner(nn.Module):
    def __init__(self, law):
        super().__init__()
        self.law = law
        self.encoder = nn.Sequential(
            nn.Linear(INPUT_DIM, 16),
            nn.Tanh(),
            nn.Linear(16, 4),
        )

    def forward(self, surface, hard=False):
        token_logits = self.encoder(surface)
        if hard:
            index = token_logits.argmax(dim=-1)
            token_dist = F.one_hot(index, num_classes=4).float()
        else:
            token_dist = torch.softmax(token_logits, dim=-1)

        state = torch.zeros(surface.shape[0], 4, device=surface.device)
        state[:, 0] = 1.0
        for step in range(surface.shape[1]):
            state = compose_distribution(state, token_dist[:, step], self.law)
        return torch.log(state + 1e-9), token_logits


class GRUReasoner(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(INPUT_DIM, 5, batch_first=True)
        self.head = nn.Linear(5, 4)

    def forward(self, surface):
        _, hidden = self.gru(surface)
        return self.head(hidden[-1])


def parameter_count(model):
    return sum(parameter.numel() for parameter in model.parameters())


def make_pair_batch(batch, length, prototypes, device):
    elements = torch.randint(0, 4, (batch, length), device=device)
    canonical_surface = sample_surface(elements, prototypes)
    canonical_target = target_c4(elements)

    row = torch.arange(batch, device=device)
    position = torch.randint(0, length, (batch,), device=device)
    changed_elements = elements.clone()
    changed_elements[row, position] = (changed_elements[row, position] + 1) % 4
    changed_surface = sample_surface(changed_elements, prototypes)
    changed_target = target_c4(changed_elements)
    return canonical_surface, canonical_target, changed_surface, changed_target


def model_logits(model, mode, surface, hard=False):
    if mode == "gru":
        return model(surface)
    logits, _ = model(surface, hard=hard)
    return logits


def counterfactual_loss(canonical_logits, changed_logits):
    canonical_probs = torch.softmax(canonical_logits, dim=1)
    expected_changed = torch.roll(canonical_probs, shifts=1, dims=1)
    return F.kl_div(
        F.log_softmax(changed_logits, dim=1),
        expected_changed,
        reduction="batchmean",
    )


@dataclass
class Metrics:
    seed: int
    mode: str
    parameter_count: int
    singleton_acc: float
    train_pair: float
    near_acc: float
    near_pair: float
    far_acc: float
    far_pair: float
    token_grounding_acc: float | None


def evaluate(model, mode, prototypes, lengths, device, batches=16, batch=256):
    accuracies = []
    pair_accuracies = []
    model.eval()
    with torch.no_grad():
        for length in lengths:
            for _ in range(batches):
                canonical_surface, canonical_target, changed_surface, changed_target = (
                    make_pair_batch(batch, length, prototypes, device)
                )
                canonical = model_logits(model, mode, canonical_surface, hard=True).argmax(dim=1)
                changed = model_logits(model, mode, changed_surface, hard=True).argmax(dim=1)
                accuracies.append((canonical == canonical_target).float().mean().item())
                pair_accuracies.append(
                    ((canonical == canonical_target) & (changed == changed_target))
                    .float()
                    .mean()
                    .item()
                )
    return mean(accuracies), mean(pair_accuracies)


def grounding_accuracy(model, prototypes, device, batches=20, batch=512):
    if not isinstance(model, StructuredReasoner):
        return None
    values = []
    model.eval()
    with torch.no_grad():
        for _ in range(batches):
            elements = torch.randint(0, 4, (batch,), device=device)
            surface = sample_surface(elements, prototypes)
            prediction = model.encoder(surface).argmax(dim=1)
            values.append((prediction == elements).float().mean().item())
    return mean(values)


def train_one(seed, mode, steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    prototypes = make_prototypes(seed, device)

    if mode == "exact_c4":
        model = StructuredReasoner("c4").to(device)
    elif mode == "wrong_v4":
        model = StructuredReasoner("v4").to(device)
    elif mode == "gru":
        model = GRUReasoner().to(device)
    else:
        raise ValueError(mode)

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)

    for step in range(steps):
        progress = step / max(steps - 1, 1)
        max_length = 2 if progress < 0.20 else 3 if progress < 0.40 else 4 if progress < 0.65 else 5
        if random.random() < ANCHOR_RATE:
            length = 1
        else:
            length = random.randint(2, max_length)

        canonical_surface, canonical_target, changed_surface, changed_target = make_pair_batch(
            256, length, prototypes, device
        )
        canonical_logits = model_logits(model, mode, canonical_surface, hard=False)
        changed_logits = model_logits(model, mode, changed_surface, hard=False)

        task = 0.5 * (
            F.cross_entropy(canonical_logits, canonical_target)
            + F.cross_entropy(changed_logits, changed_target)
        )
        cf = counterfactual_loss(canonical_logits, changed_logits)
        loss = task + 0.25 * cf

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

    singleton_acc, _ = evaluate(model, mode, prototypes, (1,), device, batches=12)
    _, train_pair = evaluate(model, mode, prototypes, (2, 3, 4, 5), device, batches=8)
    near_acc, near_pair = evaluate(model, mode, prototypes, NEAR_LENGTHS, device)
    far_acc, far_pair = evaluate(model, mode, prototypes, FAR_LENGTHS, device)
    ground = grounding_accuracy(model, prototypes, device)

    return Metrics(
        seed=seed,
        mode=mode,
        parameter_count=parameter_count(model),
        singleton_acc=singleton_acc,
        train_pair=train_pair,
        near_acc=near_acc,
        near_pair=near_pair,
        far_acc=far_acc,
        far_pair=far_pair,
        token_grounding_acc=ground,
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

    summary = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        summary[mode] = {"parameter_count": mode_rows[0]["parameter_count"]}
        for metric in (
            "singleton_acc",
            "train_pair",
            "near_acc",
            "near_pair",
            "far_acc",
            "far_pair",
        ):
            values = [row[metric] for row in mode_rows]
            summary[mode][metric] = {"mean": mean(values), "sd": pstdev(values)}
        grounds = [
            row["token_grounding_acc"]
            for row in mode_rows
            if row["token_grounding_acc"] is not None
        ]
        if grounds:
            summary[mode]["token_grounding_acc"] = {
                "mean": mean(grounds),
                "sd": pstdev(grounds),
            }

    payload = {
        "experiment": {
            "successor_to": "PR #156 v10 paired-grounding FAIL",
            "claim": "10% length-one sequence anchors stabilize exact-algebra neural grounding",
            "fresh_seeds": list(SEEDS),
            "anchor_rate": ANCHOR_RATE,
            "train_curriculum": "10% length-one anchors; otherwise paired lengths 2->5",
            "near_lengths": list(NEAR_LENGTHS),
            "far_lengths": list(FAR_LENGTHS),
            "supervision": "sequence labels only; no separate encoder/token-label loss",
            "counterfactual_loss": "same output-level +1 relation for all model families",
            "scope_limit": "synthetic surfaces; not natural language",
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
