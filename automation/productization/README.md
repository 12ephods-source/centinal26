# Productization engine v1

This subsystem implements account goal G28 as a bounded decision and accounting primitive.

## Candidate ranking

`ProductCandidate` accepts explicit evidence references plus six bounded 0-100 policy inputs:

- measurable value signal;
- labor reduction;
- validation strength;
- MVP readiness;
- implementation cost;
- risk.

The deterministic priority score is:

`30*value + 20*labor + 20*validation + 20*readiness - 5*cost - 5*risk`

The score is a prioritization heuristic only. It is not a market valuation, profitability estimate, demand measurement, or revenue claim. Inputs must come from separately preserved evidence; the engine verifies presence and numeric bounds, not semantic truth of that evidence.

Identical candidate replay is idempotent. Conflicting records using the same candidate ID fail closed.

## MVP and validation

MVP completion and validation are separate states. A validation gate cannot pass before the MVP is complete. A candidate reaches `VALIDATED_MVP` only when both are explicit.

## Revenue boundary

`RevenueTransaction` records transaction identity, candidate identity, currency, amount in minor units, evidence references, settlement state, and independent-verification state.

`realized_revenue()` counts a transaction only when both `settled=true` and `independently_verified=true`. Unsettled or unverified records contribute zero. Duplicate identical transactions are idempotent; conflicting transaction identities fail closed.

The module cannot independently contact or authenticate a payment provider. The verification flag may be set only by a separate verifier after checking provider/transaction evidence. Therefore absence of verified transaction evidence means zero reported realized revenue, not inferred revenue.

## Current product candidates

G15 Test-a-Theory and G18 Creative Canon Engine remain separate product goals. This engine does not fabricate normalized market scores for them. They should be ranked only after measurable candidate evidence is available; engineering readiness can guide build order separately through G27.
