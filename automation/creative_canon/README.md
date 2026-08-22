# Creative Canon Engine v1

The Creative Canon Engine stores narrative canon as immutable typed facts on explicit branches.

A `CanonFact` is keyed by entity + attribute and carries a JSON-serializable value plus non-empty provenance references. Existing facts are never edited in place. A change creates a new fact and may explicitly supersede an older fact with the same entity/attribute key.

`CanonBranch` records parentage. Child branches inherit visible parent facts but can supersede an inherited fact without changing the parent branch. Sibling-branch facts cannot supersede each other.

When multiple active facts in one branch lineage assert different values for the same entity/attribute and no explicit supersession resolves them, the engine reports a contradiction and omits that key from the resolved snapshot. It never silently chooses a preferred conflicting value.

Identical semantic values may coexist without producing a false contradiction. Stable branch/fact IDs are immutable: replay of an identical record is idempotent, while changed content under the same ID fails closed.

This engine preserves canon structure and provenance. It does not decide artistic quality, factual truth outside the fictional canon, copyright/license status, or whether one creative variant should be preferred over another.
