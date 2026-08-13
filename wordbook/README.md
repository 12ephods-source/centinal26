# Wordbook

Wordbook is a local-first personal language intelligence system: a living corpus of the user's language exposure rather than a static dictionary or flashcard list.

Core product loop:

`Capture -> Contextualize -> Explain -> Practice -> Revisit -> Evolve`

The `Evolve` step is implemented as a canonical 100-generation accumulated-corpus program:

`G0 -> C1 -> G1 -> C2 -> ... -> C100 -> G100`

It is intentionally **not** 100 copies of one loop. Each cycle has a distinct objective, stage, required measurements, parent-generation requirement, and evidence record. Later cycles inherit all accepted corpus state from earlier cycles.

See `docs/WORDOOK_100_CYCLE_ENGINE.md` and `src/wordbook/evolution.py`.

Current status: core lineage/schedule contract implemented; linguistic workers and UI remain separate implementation layers. No cycle result may be represented as executed merely because the schedule exists.
