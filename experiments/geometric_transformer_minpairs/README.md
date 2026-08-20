# Token-Level Transformer Minimal-Pair Geometry Gate

## Motivation

The recurrent symbolic toy line produced a positive seed-local result but failed fresh-seed long-horizon replication. This experiment changes the model class rather than tuning that toy: a small causal Transformer operates directly on tokenized relation statements.

## Task

Each example contains a load-bearing entity chain:

`E0 REL E1 ; E1 REL E2 ; ... ; QUERY E0 En`

where `POS` preserves polarity and `NEG` flips it. Separate distractor relation statements use unrelated entities and must not affect the answer.

A canonical/perturbed pair flips exactly one load-bearing relation token, so the correct answer must flip. An invariant pair flips only a distractor relation token, so the correct answer must remain unchanged.

## Model

- 2 Transformer encoder layers used with a causal attention mask
- `d_model=64`
- 4 attention heads
- feed-forward width 128
- no dropout
- token + positional embeddings
- shared 2-D projection for geometry measurement and final answer readout

## Matched conditions

1. `baseline`: task loss only.
2. `correct_geo`: cumulative true relation parity is supervised in the shared 2-D subspace at each load-bearing relation position and at the query position.
3. `wrong_geo`: identical machinery, but with deliberately wrong semantics where POS flips and NEG preserves.

All arms use the same architecture, optimizer, training examples, training steps, seed set, and evaluation procedure.

## Frozen split

- training relation-chain lengths: 2–4
- OOD relation-chain lengths: 6 and 8
- fresh seeds: 211, 212, 213
- training steps: 400
- distractors: 0–2 during training; exactly 2 in pair evaluation

## Preregistered PASS gate

All must hold on length-8 OOD evaluation:

- mean correct pair accuracy > baseline + 0.10;
- mean correct ordinary OOD accuracy > baseline + 0.08;
- correct distractor-invariance accuracy is not worse than baseline by more than 0.03;
- mean correct pair accuracy > wrong + 0.10;
- mean correct ordinary OOD accuracy > wrong + 0.08;
- at least 2 of 3 seeds individually show correct pair accuracy > baseline + 0.05 and > wrong + 0.05.

The checker is committed before the first full GitHub execution. If the gate fails, the experiment remains a failed hypothesis; thresholds are not edited post-result.

## Scope

A PASS would show only that task-aligned hidden-state geometry can improve compositional generalization in this small synthetic Transformer experiment. It would not establish Sophontic's proprietary implementation, frontier-model scaling, 60x efficiency, or data-center obsolescence.
