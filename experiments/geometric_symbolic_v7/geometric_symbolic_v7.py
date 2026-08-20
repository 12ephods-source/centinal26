"""Data-driven selection among exact structural hypotheses.

Candidate structures are trained from task data without telling the selector
which family is correct. The final evaluation uses the hard-selected candidate,
not the soft training mixture. A reciprocal V4-labeled control task checks that
the selector follows data rather than a built-in preference for C4.

This is finite-library structure selection, not unrestricted algebra discovery
and not a Sophontic reproduction.
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

FAMILIES = ("c4", "v4", "generic", "independent")
TASKS = ("c4", "v4")
SEEDS = (50, 51, 52)
NEAR_LENGTHS = (11, 12, 13)
FAR_LENGTHS = (61, 62, 63)


def permutation_matrix(mapping):
    matrix = torch.zeros(4, 4)
    for source, target in enumerate(mapping):
        matrix[target, source] = 1.0
    return matrix


def c4_operators():
    return torch.stack(
        [
            permutation_matrix([(value + shift) % 4 for value in range(4)])
            for shift in range(4)
        ]
    )


def v4_operators():
    return torch.stack(
        [
            permutation_matrix([value ^ element for value in range(4)])
            for element in range(4)
        ]
    )


def generic_operators():
    mappings = (
        (0, 1, 2, 3),
        (1, 0, 2, 3),
        (0, 2, 1, 3),
        (0, 1, 3, 2),
    )
    return torch.stack([permutation_matrix(mapping) for mapping in mappings])


class Candidate(nn.Module):
    def __init__(self, family):
        super().__init__()
        self.family = family
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
        if self.family == "independent":
            skew = self.raw_independent - self.raw_independent.transpose(-1, -2)
            return torch.matrix_exp(0.35 * skew)

        if self.family == "c4":
            fixed = self.c4_fixed
        elif self.family == "v4":
            fixed = self.v4_fixed
        elif self.family == "generic":
            fixed = self.generic_fixed
        else:
            raise ValueError(self.family)

        basis = self.basis()
        return basis.unsqueeze(0) @ fixed @ basis.transpose(-1, -2).unsqueeze(0)

    def forward(self, tokens):
        operators = self.operators()
        state = self.start.expand(tokens.shape[0], -1)
        for step in range(tokens.shape[1]):
            operator = operators[tokens[:, step]]
            state = torch.bmm(operator, state.unsqueeze(-1)).squeeze(-1)
        return self.head(state)


class StructureSelector(nn.Module):
    def __init__(self):
        super().__init__()
        self.candidates = nn.ModuleDict({family: Candidate(family) for family in FAMILIES})
        self.selector_logits = nn.Parameter(torch.zeros(len(FAMILIES)))

    def candidate_logits(self, tokens):
        return torch.stack([self.candidates[family](tokens) for family in FAMILIES], dim=0)

    def mixed_logits(self, tokens, temperature):
        logits = self.candidate_logits(tokens)
        weights = torch.softmax(self.selector_logits / temperature, dim=0)
        return (weights[:, None, None] * logits).sum(dim=0), weights


def target_for(tokens, law):
    if law == "c4":
        return tokens.sum(dim=1) % 4
    if law == "v4":
        target = torch.zeros(tokens.shape[0], device=tokens.device, dtype=torch.long)
        for step in range(tokens.shape[1]):
            target = target ^ tokens[:, step]
        return target
    raise ValueError(law)


def make_batch(batch, min_len, max_len, device, law, fixed_len=None):
    length = fixed_len if fixed_len is not None else random.randint(min_len, max_len)
    tokens = torch.randint(0, 4, (batch, length), device=device)
    return tokens, target_for(tokens, law)


def make_pairs(batch, length, device, law):
    tokens, target = make_batch(batch, length, length, device, law, fixed_len=length)
    row = torch.arange(batch, device=device)
    position = torch.randint(0, length, (batch,), device=device)
    perturbed = tokens.clone()
    perturbed[row, position] = (perturbed[row, position] + 1) % 4
    perturbed_target = target_for(perturbed, law)
    return tokens, target, perturbed, perturbed_target


def eval_candidate(candidate, device, law, lengths, batches=12, batch=256):
    candidate.eval()
    accuracies = []
    pair_accuracies = []
    with torch.no_grad():
        for length in lengths:
            for _ in range(batches):
                tokens, target, perturbed, perturbed_target = make_pairs(
                    batch, length, device, law
                )
                canonical = candidate(tokens).argmax(dim=1)
                changed = candidate(perturbed).argmax(dim=1)
                accuracies.append((canonical == target).float().mean().item())
                pair_accuracies.append(
                    (
                        (canonical == target)
                        & (changed == perturbed_target)
                    )
                    .float()
                    .mean()
                    .item()
                )
    return mean(accuracies), mean(pair_accuracies)


@dataclass
class Metrics:
    seed: int
    task: str
    selected_family: str
    correct_family_probability: float
    selection_probability: float
    train_acc: float
    near_acc: float
    near_pair: float
    far_acc: float
    far_pair: float


def train_one(seed, task, warmup_steps, selection_steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    model = StructureSelector().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)

    # Warm every candidate equally so the selector is not determined by an
    # arbitrary initialization race.
    for _ in range(warmup_steps):
        tokens, target = make_batch(256, 1, 4, device, task)
        candidate_logits = model.candidate_logits(tokens)
        loss = torch.stack(
            [F.cross_entropy(candidate_logits[index], target) for index in range(len(FAMILIES))]
        ).mean()
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

    for step in range(selection_steps):
        tokens, target = make_batch(256, 1, 4, device, task)
        fraction = step / max(selection_steps - 1, 1)
        temperature = 1.0 - 0.8 * fraction
        mixed_logits, weights = model.mixed_logits(tokens, temperature)
        entropy = -(weights * torch.log(weights + 1e-9)).sum()
        loss = F.cross_entropy(mixed_logits, target) + 0.03 * entropy
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

    probabilities = torch.softmax(model.selector_logits / 0.2, dim=0).detach().cpu()
    selected_index = int(probabilities.argmax().item())
    selected_family = FAMILIES[selected_index]
    selected = model.candidates[selected_family]

    train_acc, _ = eval_candidate(selected, device, task, (4,), batches=8)
    near_acc, near_pair = eval_candidate(selected, device, task, NEAR_LENGTHS)
    far_acc, far_pair = eval_candidate(selected, device, task, FAR_LENGTHS)
    correct_index = FAMILIES.index(task)

    return Metrics(
        seed=seed,
        task=task,
        selected_family=selected_family,
        correct_family_probability=float(probabilities[correct_index].item()),
        selection_probability=float(probabilities[selected_index].item()),
        train_acc=train_acc,
        near_acc=near_acc,
        near_pair=near_pair,
        far_acc=far_acc,
        far_pair=far_pair,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup-steps", type=int, default=250)
    parser.add_argument("--selection-steps", type=int, default=350)
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    torch.set_num_threads(1)
    device = torch.device("cpu")
    rows = []

    for task in TASKS:
        for seed in SEEDS:
            row = asdict(
                train_one(seed, task, args.warmup_steps, args.selection_steps, device)
            )
            rows.append(row)
            print(json.dumps(row))

    summary = {}
    for task in TASKS:
        task_rows = [row for row in rows if row["task"] == task]
        summary[task] = {
            "correct_selection_rate": mean(
                1.0 if row["selected_family"] == task else 0.0 for row in task_rows
            ),
        }
        for metric in (
            "correct_family_probability",
            "selection_probability",
            "train_acc",
            "near_acc",
            "near_pair",
            "far_acc",
            "far_pair",
        ):
            values = [row[metric] for row in task_rows]
            summary[task][metric] = {"mean": mean(values), "sd": pstdev(values)}

    payload = {
        "experiment": {
            "successor_to": "PR #151 exact-algebra reference PASS",
            "claim": "finite-library exact-structure selection from data",
            "candidate_families": list(FAMILIES),
            "tasks": list(TASKS),
            "fresh_seeds": list(SEEDS),
            "near_lengths": list(NEAR_LENGTHS),
            "far_lengths": list(FAR_LENGTHS),
            "evaluation": "hard-selected candidate only",
            "scope_limit": "candidate selection, not unrestricted algebra discovery",
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
