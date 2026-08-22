# Lane A singleton-anchor reconciliation — 2026-08-22

This record consolidates the stale stacked singleton-anchor research sequence onto current `main` without merging its historical branch ancestry and without changing any frozen scientific threshold.

## Evidence status

For PRs #158, #161, #165, #166, #167, #168, and #169, the PASS/FAIL labels below are the frozen states stated in their PR descriptions and are preserved as historical project evidence. PR #170 was independently re-read during this reconciliation from its exact-head GitHub Actions run and job log.

The sequence is:

- #158 / v11 / 10% anchors: reported PASS.
- #161 / v12 / 2%: reported FAIL.
- #165 / v13 / 5%: reported FAIL.
- #166 / v14 / 7.5%: reported PASS.
- #167 / v15 / 6.25%: reported FAIL.
- #168 / v16 / 6.875%: reported PASS.
- #169 / v17 / matched 6.25% vs 6.875% over 12 fresh seeds: reported FAIL of the stronger dose-boundary replication claim.
- #170 / v18 / confirmatory 10% over 12 fresh seeds: independently confirmed scientific FAIL under the preregistered aggregate gate.

## Exact v18 result

Head: `f4f4f9b5ff6387bdb2a11ab925d5a0675f2722fa`.

All standard repository workflows passed. The dedicated `geometric-symbolic-v18` workflow ran the frozen experiment successfully, ran the checker successfully, recorded environment and hashes, and uploaded evidence. The workflow failed only at the final step that enforces the scientific verdict.

The exact-C4 arm was individually reliable on 10/12 seeds. It exceeded the wrong-V4 far-pair result by >0.20 on 10/12 seeds and exceeded the GRU by >0.20 on 11/12. Nevertheless, the preregistered aggregate conditions failed:

- mean exact far-pair accuracy = `0.8756849500868056`, below `0.90`;
- mean exact token grounding = `0.9081461588541666`, below `0.98`.

Therefore v18 is a genuine negative reliability result, not an infrastructure failure and not a reason to change thresholds after seeing the data.

## Current interpretation

The chain supports a narrower statement than the original positive v11 result alone: the supplied exact-C4 structure can produce strong synthetic compositional performance and large control margins on many seeds, but convergence/reliability is seed-sensitive. The stronger matched and confirmatory replications do not establish a universal anchor-dose threshold or unconditional reliability at 10%.

Nothing in this chain establishes natural-language reasoning, frontier-model generalization, Sophontic replication, training-FLOP efficiency, 60x/1000x efficiency, or data-center obsolescence.

## Supersession rule

After the companion machine-readable ledger is exact-head qualified, merged, and verified on `main`, PRs #158, #161, #165, #166, #167, #168, #169, and #170 may be closed as superseded research records. Closing them preserves their outcomes; it does not turn scientific FAIL results into PASS results or erase earlier bounded positive results.
