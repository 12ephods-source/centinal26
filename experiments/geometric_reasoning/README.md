# Geometric Reasoning — Falsification Prototype

Date: 2026-08-18

## Question
Can explicit latent-geometry constraints improve compositional generalization, independent of model size and architecture?

## Design
Same recurrent neural architecture and optimizer in three conditions:

1. **baseline** — task loss only.
2. **correct_geo** — task loss plus latent transition compactness, correct inverse-pair constraints, axis separation, and inverse-cycle consistency.
3. **wrong_geo** — same regularization machinery but with deliberately false geometric relations.

Synthetic task: start from a 2D integer coordinate and compose primitive translations R/L/U/D. Training sees chains of length 1–3. OOD evaluation uses chains of length 8 and 16. Five random seeds; 700 training steps per condition/seed.

This is a mechanistic toy test, not an LLM benchmark and not a reproduction of Sophontic.

## Results (5 seeds)

| Condition | Train MSE | OOD-8 MSE | OOD-16 MSE | OOD-16 MAE | OOD-16 exact | Transition delta CV |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.00712 | 0.09194 | 0.62180 | 0.57561 | 0.3200 | 0.2319 |
| correct_geo | 0.00521 | 0.06699 | 0.33361 | 0.33633 | 0.7446 | 0.1057 |
| wrong_geo | 0.01054 | 0.12427 | 1.05215 | 0.78144 | 0.1657 | 0.2211 |

Derived effect sizes:

- Correct geometry reduced OOD-16 MSE by **46.35%** vs baseline.
- Correct geometry improved OOD-16 exact accuracy by **42.46 percentage points** (0.3200 → 0.7446), a **2.33×** ratio.
- Correct geometry reduced transition-delta coefficient of variation by **54.42%**, meaning operation effects became substantially more state-invariant in latent space.
- Wrong geometry increased OOD-16 MSE by **69.21%** vs baseline.

## Interpretation

### Observed
Under this controlled toy task, explicitly correct geometric constraints substantially improved long-horizon compositional generalization. Incorrect geometric constraints damaged it. Because architecture, parameter count, optimizer, and task are matched, this isolates the geometry prior as a plausible causal contributor within this experiment.

### Derived
The improvement is associated with more consistent latent operation vectors: delta-CV falls from ~0.232 to ~0.106 under the correct geometry objective.

### Not established
This does **not** establish that:

- Sophontic uses this exact mechanism;
- the effect survives on language reasoning tasks;
- a 124M model can beat 7B models generally;
- geometric training produces 60× or 1000× compute efficiency;
- AI data centers become obsolete.

## Falsification value
The wrong-geometry control matters because a generic regularization explanation predicts that any additional regularizer might help. Instead, deliberately false structure performs worse than baseline on the principal OOD metric. This supports the stronger hypothesis that *the correctness of the imposed latent algebra matters*.

## Reproduction gate
CI reruns the three matched conditions and then applies an explicit verifier. A PASS requires, at minimum:

- correct geometry OOD-16 MSE < 0.80 × baseline OOD-16 MSE;
- correct geometry exact-16 accuracy > baseline by 0.20 absolute;
- correct geometry transition delta CV < baseline;
- wrong geometry OOD-16 MSE > 1.05 × baseline.

The thresholds are preregistered in `verify_geometric_reasoning.py`. A CI PASS is an execution/numerical result for this toy experiment only; it is not evidence of Sophontic replication.

## Next gate
Move from Euclidean translation composition to symbolic logical reasoning while retaining the same three-way matched experiment:

- baseline task loss;
- correct latent-operator geometry;
- deliberately wrong latent geometry.

Use canonical/perturbed reasoning pairs, held-out operation compositions, matched parameters/FLOPs, and pair-level accuracy. Only after that gate should a transformer-scale experiment be justified.
