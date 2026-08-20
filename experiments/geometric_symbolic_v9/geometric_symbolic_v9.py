"""Neural surface encoder + exact latent algebra versus matched controls.

Each latent C4 element is observed only through a noisy continuous feature
vector. Training receives sequence-level composition labels, never per-token
latent labels. The structured model learns a surface encoder and composes its
latent categorical predictions using an exact C4 law. Controls are an otherwise
identical encoder with the wrong exact V4 law and a parameter-matched GRU.

This is a synthetic neural-grounding/sample-efficiency bridge, not natural
language and not a Sophontic reproduction.
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
SEEDS = (70, 71, 72)
TRAIN_LENGTHS = (2, 3, 4, 5)
NEAR_LENGTHS = (11, 12, 13)
FAR_LENGTHS = (61, 62, 63)
INPUT_DIM = 12
NOISE_STD = 0.12


def make_prototypes(seed, device):
    generator = torch.Generator(device=device)
    generator.manual_seed(seed + 1000)
    raw = torch.randn(4, INPUT_DIM, generator=generator, device=device)
    return F.normalize(raw, dim=1) * 3.0


def sample_surface(elements, prototypes, noise_std=NOISE_STD):
    base = prototypes[elements]
    return base + noise_std * torch.randn_like(base)


def target_c4(elements):
    return elements.sum(dim=1) % 4


def make_batch(batch, lengths, prototypes, device, fixed_len=None):
    length = fixed_len if fixed_len is not None else random.choice(lengths)
    elements = torch.randint(0, 4, (batch, length), device=device)
    surface = sample_surface(elements, prototypes)
    target = target_c4(elements)
    return surface, elements, target


def compose_distribution(state, token_dist, law):
    result = torch.zeros_like(state)
    for left in range(4):
        for right in range(4):
            if law == "c4":
                target = (left + right) % 4
            elif law == "v4":
                target = left ^ right
            else:
                raise ValueError(law)
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

    def token_logits(self, surface):
        return self.encoder(surface)

    def forward(self, surface, hard=False):
        batch, length, _ = surface.shape
        logits = self.token_logits(surface)
        if hard:
            indices = logits.argmax(dim=-1)
            token_dist = F.one_hot(indices, num_classes=4).float()
        else:
            token_dist = torch.softmax(logits, dim=-1)

        state = torch.zeros(batch, 4, device=surface.device)
        state[:, 0] = 1.0
        for step in range(length):
            state = compose_distribution(state, token_dist[:, step], self.law)
        return torch.log(state + 1e-9), logits


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


@dataclass
class Metrics:
    seed: int
    mode: str
    parameter_count: int
    train_acc: float
    near_acc: float
    near_pair: float
    far_acc: float
    far_pair: float
    token_grounding_acc: float | None


def make_pairs(batch, length, prototypes, device):
    elements = torch.randint(0, 4, (batch, length), device=device)
    target = target_c4(elements)
    surface = sample_surface(elements, prototypes)

    row = torch.arange(batch, device=device)
    position = torch.randint(0, length, (batch,), device=device)
    changed_elements = elements.clone()
    changed_elements[row, position] = (changed_elements[row, position] + 1) % 4
    changed_target = target_c4(changed_elements)
    changed_surface = sample_surface(changed_elements, prototypes)
    return surface, target, changed_surface, changed_target


def predict(model, mode, surface):
    if mode == "gru":
        return model(surface).argmax(dim=1)
    logits, _ = model(surface, hard=True)
    return logits.argmax(dim=1)


def eval_lengths(model, mode, prototypes, lengths, device, batches=16, batch=256):
    accuracies = []
    pair_accuracies = []
    model.eval()
    with torch.no_grad():
        for length in lengths:
            for _ in range(batches):
                surface, target, changed_surface, changed_target = make_pairs(
                    batch, length, prototypes, device
                )
                canonical = predict(model, mode, surface)
                changed = predict(model, mode, changed_surface)
                accuracies.append((canonical == target).float().mean().item())
                pair_accuracies.append(
                    ((canonical == target) & (changed == changed_target))
                    .float()
                    .mean()
                    .item()
                )
    return mean(accuracies), mean(pair_accuracies)


def token_grounding_accuracy(model, prototypes, device, batches=20, batch=512):
    if not isinstance(model, StructuredReasoner):
        return None
    values = []
    model.eval()
    with torch.no_grad():
        for _ in range(batches):
            elements = torch.randint(0, 4, (batch,), device=device)
            surface = sample_surface(elements, prototypes)
            logits = model.encoder(surface)
            values.append((logits.argmax(dim=1) == elements).float().mean().item())
    return mean(values)


def train_one(seed, mode, steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    prototypes = make_prototypes(seed, device)

    if mode == "gru":
        model = GRUReasoner().to(device)
    elif mode == "exact_c4":
        model = StructuredReasoner("c4").to(device)
    elif mode == "wrong_v4":
        model = StructuredReasoner("v4").to(device)
    else:
        raise ValueError(mode)

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)

    for _ in range(steps):
        model.train()
        surface, _, target = make_batch(256, TRAIN_LENGTHS, prototypes, device)
        if mode == "gru":
            logits = model(surface)
        else:
            logits, _ = model(surface, hard=False)
        loss = F.cross_entropy(logits, target)
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

    train_acc, _ = eval_lengths(model, mode, prototypes, TRAIN_LENGTHS, device, batches=8)
    near_acc, near_pair = eval_lengths(model, mode, prototypes, NEAR_LENGTHS, device)
    far_acc, far_pair = eval_lengths(model, mode, prototypes, FAR_LENGTHS, device)
    grounding = token_grounding_accuracy(model, prototypes, device)

    return Metrics(
        seed=seed,
        mode=mode,
        parameter_count=parameter_count(model),
        train_acc=train_acc,
        near_acc=near_acc,
        near_pair=near_pair,
        far_acc=far_acc,
        far_pair=far_pair,
        token_grounding_acc=grounding,
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

    summary = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        summary[mode] = {
            "parameter_count": mode_rows[0]["parameter_count"],
        }
        for metric in ("train_acc", "near_acc", "near_pair", "far_acc", "far_pair"):
            values = [row[metric] for row in mode_rows]
            summary[mode][metric] = {"mean": mean(values), "sd": pstdev(values)}
        grounding_values = [
            row["token_grounding_acc"]
            for row in mode_rows
            if row["token_grounding_acc"] is not None
        ]
        if grounding_values:
            summary[mode]["token_grounding_acc"] = {
                "mean": mean(grounding_values),
                "sd": pstdev(grounding_values),
            }

    payload = {
        "experiment": {
            "successor_to": "PR #153 hidden-mapping finite-library PASS",
            "claim": "neural surface grounding into an exact latent algebra",
            "input_dim": INPUT_DIM,
            "noise_std": NOISE_STD,
            "training_lengths": list(TRAIN_LENGTHS),
            "near_lengths": list(NEAR_LENGTHS),
            "far_lengths": list(FAR_LENGTHS),
            "fresh_seeds": list(SEEDS),
            "training_supervision": "sequence labels only; no token latent labels",
            "scope_limit": "synthetic continuous surfaces; not natural language",
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
