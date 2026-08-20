"""Tiny-transformer minimal-pair test for latent reasoning geometry.

This experiment follows the failed recurrent toy line with a qualitatively
new model class: a causal Transformer operating on tokenized relation chains.

Task semantics:
- POS preserves logical polarity.
- NEG flips logical polarity.
- The target is the parity/product of the load-bearing relation chain.
- Distractor relation statements use separate entities and are irrelevant.
- A canonical/perturbed pair flips exactly one load-bearing relation token.

Matched arms:
- baseline: answer loss only.
- correct_geo: cumulative chain parity is supervised in a task-aligned 2-D
  hidden-state projection at each load-bearing relation position.
- wrong_geo: the same loss supervises the deliberately wrong algebra in which
  POS flips and NEG preserves.

The answer logit is read directly from the same 2-D projection, coupling the
structured subspace to prediction.

This is a toy mechanistic experiment, not a Sophontic reproduction.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from statistics import mean, pstdev

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

MODES = ("baseline", "correct_geo", "wrong_geo")

PAD = 0
BOS = 1
POS = 2
NEG = 3
SEP = 4
QUERY = 5
DIST_POS = 6
DIST_NEG = 7
ENTITY_BASE = 8
N_ENTITY = 40
VOCAB = ENTITY_BASE + N_ENTITY


class TinyReasoningTransformer(nn.Module):
    def __init__(self, d_model: int = 64, nhead: int = 4, layers: int = 2, max_len: int = 96):
        super().__init__()
        self.token_emb = nn.Embedding(VOCAB, d_model)
        self.pos_emb = nn.Embedding(max_len, d_model)
        block = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=128,
            dropout=0.0,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(block, num_layers=layers)
        self.proj = nn.Linear(d_model, 2)
        self.logit_scale = nn.Parameter(torch.tensor(1.0))

    def forward(self, tokens, pad_mask=None):
        batch, length = tokens.shape
        pos = torch.arange(length, device=tokens.device).unsqueeze(0).expand(batch, -1)
        h = self.token_emb(tokens) + self.pos_emb(pos)
        causal = torch.full((length, length), float("-inf"), device=tokens.device)
        causal = torch.triu(causal, diagonal=1)
        h = self.encoder(h, mask=causal, src_key_padding_mask=pad_mask)
        return h

    def z(self, h):
        return self.proj(h)

    def answer_logits(self, h, query_pos):
        batch_idx = torch.arange(h.shape[0], device=h.device)
        zq = self.z(h[batch_idx, query_pos])
        return self.logit_scale * zq[:, 0]


def ent(i):
    return ENTITY_BASE + i


def build_example(chain_len, n_distractors, rng):
    entities = list(range(chain_len + 1))
    edges = [rng.randrange(2) for _ in range(chain_len)]
    tokens = [BOS]
    rel_positions = []
    cumulative = []
    parity = 0

    for i, edge in enumerate(edges):
        tokens.extend([ent(entities[i]), POS if edge == 0 else NEG, ent(entities[i + 1]), SEP])
        rel_positions.append(len(tokens) - 3)
        parity ^= edge
        cumulative.append(parity)

    distractor_pool = list(range(20, 40))
    rng.shuffle(distractor_pool)
    for j in range(n_distractors):
        left = distractor_pool[(2 * j) % len(distractor_pool)]
        right = distractor_pool[(2 * j + 1) % len(distractor_pool)]
        rel = DIST_POS if rng.randrange(2) == 0 else DIST_NEG
        tokens.extend([ent(left), rel, ent(right), SEP])

    tokens.extend([QUERY, ent(entities[0]), ent(entities[-1])])
    query_pos = len(tokens) - 3
    target = 1.0 if parity == 0 else -1.0

    return {
        "tokens": tokens,
        "edges": edges,
        "rel_positions": rel_positions,
        "cumulative": cumulative,
        "query_pos": query_pos,
        "target": target,
    }


def collate(examples, device):
    max_len = max(len(ex["tokens"]) for ex in examples)
    tokens = torch.full((len(examples), max_len), PAD, dtype=torch.long, device=device)
    pad_mask = torch.ones((len(examples), max_len), dtype=torch.bool, device=device)
    query_pos = []
    targets = []
    for i, ex in enumerate(examples):
        seq = torch.tensor(ex["tokens"], dtype=torch.long, device=device)
        tokens[i, : len(seq)] = seq
        pad_mask[i, : len(seq)] = False
        query_pos.append(ex["query_pos"])
        targets.append(ex["target"])
    return (
        tokens,
        pad_mask,
        torch.tensor(query_pos, dtype=torch.long, device=device),
        torch.tensor(targets, dtype=torch.float32, device=device),
    )


def sample_batch(batch_size, min_len, max_len, max_distractors, rng, device, fixed_len=None):
    examples = []
    for _ in range(batch_size):
        length = fixed_len if fixed_len is not None else rng.randint(min_len, max_len)
        n_dist = rng.randint(0, max_distractors)
        examples.append(build_example(length, n_dist, rng))
    return examples, collate(examples, device)


def geometry_loss(model, h, examples, mode, device):
    if mode == "baseline":
        return torch.tensor(0.0, device=device)

    losses = []
    for b, ex in enumerate(examples):
        for pos, true_parity in zip(ex["rel_positions"], ex["cumulative"]):
            if mode == "correct_geo":
                parity = true_parity
            else:
                # Deliberately wrong algebra: POS flips, NEG preserves.
                prefix = ex["edges"][: ex["rel_positions"].index(pos) + 1]
                parity = sum(1 - edge for edge in prefix) % 2

            target = torch.tensor(
                [1.0 if parity == 0 else -1.0, 0.0],
                dtype=h.dtype,
                device=device,
            )
            losses.append(F.mse_loss(model.z(h[b, pos]), target))

        q_target_parity = ex["cumulative"][-1]
        if mode == "wrong_geo":
            q_target_parity = sum(1 - edge for edge in ex["edges"]) % 2
        q_target = torch.tensor(
            [1.0 if q_target_parity == 0 else -1.0, 0.0],
            dtype=h.dtype,
            device=device,
        )
        losses.append(F.mse_loss(model.z(h[b, ex["query_pos"]]), q_target))

    return torch.stack(losses).mean()


@dataclass
class Metrics:
    seed: int
    mode: str
    train4_acc: float
    ood6_acc: float
    ood8_acc: float
    pair6_acc: float
    pair8_acc: float
    invariant8_acc: float


def prediction(logits):
    return torch.where(logits >= 0, 1.0, -1.0)


def evaluate_plain(model, seed, length, device, batches=12, batch_size=128):
    rng = random.Random(seed)
    model.eval()
    scores = []
    with torch.no_grad():
        for _ in range(batches):
            examples, packed = sample_batch(
                batch_size, length, length, 2, rng, device, fixed_len=length
            )
            del examples
            tokens, pad_mask, query_pos, targets = packed
            h = model(tokens, pad_mask)
            logits = model.answer_logits(h, query_pos)
            scores.append((prediction(logits) == targets).float().mean().item())
    return mean(scores)


def mutate_example(ex, rng, load_bearing):
    out = {
        "tokens": list(ex["tokens"]),
        "edges": list(ex["edges"]),
        "rel_positions": list(ex["rel_positions"]),
        "cumulative": list(ex["cumulative"]),
        "query_pos": ex["query_pos"],
        "target": ex["target"],
    }
    if load_bearing:
        idx = rng.randrange(len(out["edges"]))
        pos = out["rel_positions"][idx]
        out["edges"][idx] ^= 1
        out["tokens"][pos] = POS if out["edges"][idx] == 0 else NEG
        parity = 0
        out["cumulative"] = []
        for edge in out["edges"]:
            parity ^= edge
            out["cumulative"].append(parity)
        out["target"] = -out["target"]
    else:
        distractor_positions = [
            i for i, tok in enumerate(out["tokens"]) if tok in (DIST_POS, DIST_NEG)
        ]
        if distractor_positions:
            pos = rng.choice(distractor_positions)
            out["tokens"][pos] = DIST_NEG if out["tokens"][pos] == DIST_POS else DIST_POS
    return out


def evaluate_pairs(model, seed, length, device, batches=12, batch_size=128):
    rng = random.Random(seed)
    model.eval()
    pair_scores = []
    invariant_scores = []
    with torch.no_grad():
        for _ in range(batches):
            originals = [build_example(length, 2, rng) for _ in range(batch_size)]
            changed = [mutate_example(ex, rng, True) for ex in originals]
            invariant = [mutate_example(ex, rng, False) for ex in originals]

            _, a_pack = originals, collate(originals, device)
            _, b_pack = changed, collate(changed, device)
            _, c_pack = invariant, collate(invariant, device)

            def run(pack):
                tokens, pad_mask, query_pos, targets = pack
                h = model(tokens, pad_mask)
                return prediction(model.answer_logits(h, query_pos)), targets

            pa, ta = run(a_pack)
            pb, tb = run(b_pack)
            pc, tc = run(c_pack)
            pair_scores.append(((pa == ta) & (pb == tb)).float().mean().item())
            invariant_scores.append(((pa == ta) & (pc == tc)).float().mean().item())

    return mean(pair_scores), mean(invariant_scores)


def train_one(seed, mode, steps, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    rng = random.Random(seed)

    model = TinyReasoningTransformer().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=1e-4)

    for step in range(steps):
        model.train()
        examples, packed = sample_batch(128, 2, 4, 2, rng, device)
        tokens, pad_mask, query_pos, targets = packed
        h = model(tokens, pad_mask)
        logits = model.answer_logits(h, query_pos)
        task = F.softplus(-targets * logits).mean()
        geo = geometry_loss(model, h, examples, mode, device)
        ramp = min(1.0, (step + 1) / 100)
        loss = task + ramp * 0.10 * geo
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

    train4 = evaluate_plain(model, seed + 1000, 4, device)
    ood6 = evaluate_plain(model, seed + 2000, 6, device)
    ood8 = evaluate_plain(model, seed + 3000, 8, device)
    pair6, _ = evaluate_pairs(model, seed + 4000, 6, device)
    pair8, invariant8 = evaluate_pairs(model, seed + 5000, 8, device)
    return Metrics(seed, mode, train4, ood6, ood8, pair6, pair8, invariant8)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--seed-start", type=int, default=211)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    torch.set_num_threads(1)
    device = torch.device("cpu")
    rows = []
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))

    for mode in MODES:
        for seed in seeds:
            row = asdict(train_one(seed, mode, args.steps, device))
            rows.append(row)
            print(json.dumps(row))

    keys = ("train4_acc", "ood6_acc", "ood8_acc", "pair6_acc", "pair8_acc", "invariant8_acc")
    summary = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        summary[mode] = {}
        for key in keys:
            values = [row[key] for row in mode_rows]
            summary[mode][key] = {"mean": mean(values), "sd": pstdev(values)}

    payload = {
        "experiment": {
            "model": "2-layer causal Transformer, d_model=64, 4 heads",
            "train_lengths": [2, 3, 4],
            "ood_lengths": [6, 8],
            "seeds": seeds,
            "steps": args.steps,
            "scope_limit": "toy token-level transformer; not Sophontic reproduction",
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
