"""Joint exact-algebra and hidden symbol-mapping selection.

Each run secretly permutes the observed token IDs before applying either the C4
or V4 group law. The learner is given 48 exact hypotheses: 2 group families x
24 token-to-group-element bijections. It trains only categorical hypothesis
weights from short composition examples (lengths 2-5; no one-step examples),
then discards the soft mixture and evaluates one hard-selected hypothesis.

This is finite-library structure+mapping identification, not unrestricted
algebra discovery and not a Sophontic reproduction.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import asdict, dataclass
from statistics import mean, pstdev

import numpy as np
import torch
import torch.nn.functional as F

FAMILIES = ("c4", "v4")
SEEDS = (60, 61, 62)
TRAIN_LENGTHS = (2, 3, 4, 5)
NEAR_LENGTHS = (11, 12, 13)
FAR_LENGTHS = (61, 62, 63)
PERMUTATIONS = tuple(itertools.permutations(range(4)))
HYPOTHESES = tuple((family, permutation) for family in FAMILIES for permutation in PERMUTATIONS)


def compose_elements(elements, family):
    if family == "c4":
        return elements.sum(dim=1) % 4
    if family == "v4":
        result = torch.zeros(elements.shape[0], device=elements.device, dtype=torch.long)
        for step in range(elements.shape[1]):
            result = result ^ elements[:, step]
        return result
    raise ValueError(family)


def map_tokens(tokens, permutation):
    table = torch.tensor(permutation, device=tokens.device, dtype=torch.long)
    return table[tokens]


def target_for(tokens, family, hidden_mapping):
    return compose_elements(map_tokens(tokens, hidden_mapping), family)


def hypothesis_prediction(tokens, family, mapping):
    return compose_elements(map_tokens(tokens, mapping), family)


def candidate_probabilities(tokens, epsilon=1e-4):
    batch = tokens.shape[0]
    probs = []
    for family, mapping in HYPOTHESES:
        prediction = hypothesis_prediction(tokens, family, mapping)
        candidate = torch.full(
            (batch, 4), epsilon / 3.0, device=tokens.device, dtype=torch.float32
        )
        candidate.scatter_(1, prediction[:, None], 1.0 - epsilon)
        probs.append(candidate)
    return torch.stack(probs, dim=0)


def make_batch(batch, lengths, device, true_family, hidden_mapping):
    length = random.choice(lengths)
    tokens = torch.randint(0, 4, (batch, length), device=device)
    target = target_for(tokens, true_family, hidden_mapping)
    return tokens, target


def select_hypothesis(seed, true_family, steps, device):
    offset = 10000 if true_family == "v4" else 0
    rng = random.Random(seed + offset)
    hidden_mapping = tuple(rng.sample(range(4), 4))

    random.seed(seed + offset)
    np.random.seed(seed + offset)
    torch.manual_seed(seed + offset)

    selector_logits = torch.zeros(len(HYPOTHESES), device=device, requires_grad=True)
    optimizer = torch.optim.Adam([selector_logits], lr=0.12)

    for step in range(steps):
        tokens, target = make_batch(384, TRAIN_LENGTHS, device, true_family, hidden_mapping)
        candidates = candidate_probabilities(tokens)
        temperature = max(0.25, 1.0 - 0.75 * step / max(steps - 1, 1))
        weights = torch.softmax(selector_logits / temperature, dim=0)
        mixture = (weights[:, None, None] * candidates).sum(dim=0)
        nll = F.nll_loss(torch.log(mixture + 1e-12), target)
        entropy = -(weights * torch.log(weights + 1e-12)).sum()
        loss = nll + 0.01 * entropy

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    final_weights = torch.softmax(selector_logits / 0.20, dim=0).detach().cpu()
    selected_index = int(final_weights.argmax().item())
    selected_family, selected_mapping = HYPOTHESES[selected_index]
    return hidden_mapping, selected_family, selected_mapping, float(final_weights[selected_index])


def eval_hypothesis(
    family,
    mapping,
    true_family,
    hidden_mapping,
    lengths,
    device,
    batches=20,
    batch=256,
):
    accuracies = []
    pair_accuracies = []
    for length in lengths:
        for _ in range(batches):
            tokens = torch.randint(0, 4, (batch, length), device=device)
            target = target_for(tokens, true_family, hidden_mapping)
            prediction = hypothesis_prediction(tokens, family, mapping)

            row = torch.arange(batch, device=device)
            position = torch.randint(0, length, (batch,), device=device)
            replacement = torch.randint(0, 3, (batch,), device=device)
            old = tokens[row, position]
            replacement = replacement + (replacement >= old).long()
            perturbed = tokens.clone()
            perturbed[row, position] = replacement
            perturbed_target = target_for(perturbed, true_family, hidden_mapping)
            perturbed_prediction = hypothesis_prediction(perturbed, family, mapping)

            accuracies.append((prediction == target).float().mean().item())
            pair_accuracies.append(
                ((prediction == target) & (perturbed_prediction == perturbed_target))
                .float()
                .mean()
                .item()
            )
    return mean(accuracies), mean(pair_accuracies)


def exhaustive_behavioral_equivalence(
    selected_family, selected_mapping, true_family, hidden_mapping, device
):
    for length in (2, 3, 4):
        sequences = torch.tensor(
            list(itertools.product(range(4), repeat=length)),
            device=device,
            dtype=torch.long,
        )
        true_target = target_for(sequences, true_family, hidden_mapping)
        selected_target = hypothesis_prediction(sequences, selected_family, selected_mapping)
        if not torch.equal(true_target, selected_target):
            return False
    return True


@dataclass
class Metrics:
    seed: int
    task: str
    hidden_mapping: list[int]
    selected_family: str
    selected_mapping: list[int]
    selection_probability: float
    behavioral_equivalence: bool
    train_acc: float
    near_acc: float
    near_pair: float
    far_acc: float
    far_pair: float


def run_one(seed, task, steps, device):
    hidden_mapping, selected_family, selected_mapping, probability = select_hypothesis(
        seed, task, steps, device
    )
    train_acc, _ = eval_hypothesis(
        selected_family,
        selected_mapping,
        task,
        hidden_mapping,
        TRAIN_LENGTHS,
        device,
        batches=8,
    )
    near_acc, near_pair = eval_hypothesis(
        selected_family,
        selected_mapping,
        task,
        hidden_mapping,
        NEAR_LENGTHS,
        device,
    )
    far_acc, far_pair = eval_hypothesis(
        selected_family,
        selected_mapping,
        task,
        hidden_mapping,
        FAR_LENGTHS,
        device,
    )
    equivalent = exhaustive_behavioral_equivalence(
        selected_family, selected_mapping, task, hidden_mapping, device
    )
    return Metrics(
        seed=seed,
        task=task,
        hidden_mapping=list(hidden_mapping),
        selected_family=selected_family,
        selected_mapping=list(selected_mapping),
        selection_probability=probability,
        behavioral_equivalence=equivalent,
        train_acc=train_acc,
        near_acc=near_acc,
        near_pair=near_pair,
        far_acc=far_acc,
        far_pair=far_pair,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=450)
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    torch.set_num_threads(1)
    device = torch.device("cpu")
    rows = []

    for task in FAMILIES:
        for seed in SEEDS:
            row = asdict(run_one(seed, task, args.steps, device))
            rows.append(row)
            print(json.dumps(row))

    summary = {}
    for task in FAMILIES:
        task_rows = [row for row in rows if row["task"] == task]
        summary[task] = {
            "correct_family_rate": mean(
                1.0 if row["selected_family"] == task else 0.0 for row in task_rows
            ),
            "behavioral_equivalence_rate": mean(
                1.0 if row["behavioral_equivalence"] else 0.0 for row in task_rows
            ),
        }
        for metric in (
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
            "successor_to": "PR #152 finite-library structure-selection PASS",
            "claim": "joint exact-family and hidden token-mapping identification",
            "hypothesis_count": len(HYPOTHESES),
            "training_lengths": list(TRAIN_LENGTHS),
            "one_step_training_excluded": True,
            "near_lengths": list(NEAR_LENGTHS),
            "far_lengths": list(FAR_LENGTHS),
            "fresh_seeds": list(SEEDS),
            "scope_limit": "finite 48-hypothesis identification; not unrestricted discovery",
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
