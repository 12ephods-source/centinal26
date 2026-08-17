import copy
import json
import unittest

from areop.controller import gate0, replay, state_hash


S0 = {
    "schema_version": "AREOP-1.0",
    "revision": 0,
    "objective": None,
    "claims": {},
    "artifacts": {},
    "active_bottleneck": None,
    "next_decisive_test": "GATE-0 deterministic evidence replay",
    "terminal_state": None,
}


def ev(seq, event_id, kind, payload):
    return {"seq": seq, "event_id": event_id, "kind": kind, "payload": payload}


class Gate0Tests(unittest.TestCase):
    def test_empty_replay_is_initial_state(self):
        self.assertEqual(replay(S0, []), S0)

    def test_replay_is_deterministic_and_hash_stable(self):
        events = [
            ev(1, "E1", "SET_OBJECTIVE", {"objective": "derive and falsify"}),
            ev(2, "E2", "UPSERT_CLAIM", {
                "claim_id": "C1", "claim": "candidate", "status": "UNKNOWN",
                "dependencies": [], "invalidation_conditions": ["counterexample"]}),
            ev(3, "E3", "SET_CLAIM_STATUS", {"claim_id": "C1", "status": "HYPOTHESIS"}),
        ]
        a = replay(S0, events)
        b = replay(copy.deepcopy(S0), json.loads(json.dumps(events)))
        self.assertEqual(a, b)
        self.assertEqual(state_hash(a), state_hash(b))
        self.assertEqual(gate0(S0, events, a)["status"], "PASS")

    def test_duplicate_event_id_fails_closed(self):
        events = [
            ev(1, "E1", "SET_OBJECTIVE", {"objective": "x"}),
            ev(2, "E1", "SET_BOTTLENECK", {"value": "y"}),
        ]
        with self.assertRaisesRegex(ValueError, "duplicate event_id"):
            replay(S0, events)

    def test_out_of_order_sequence_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "sequence mismatch"):
            replay(S0, [ev(2, "E2", "SET_OBJECTIVE", {"objective": "x"})])

    def test_illegal_promotion_jump_fails_closed(self):
        events = [
            ev(1, "E1", "UPSERT_CLAIM", {"claim_id": "C1", "claim": "x", "status": "UNKNOWN"}),
            ev(2, "E2", "SET_CLAIM_STATUS", {"claim_id": "C1", "status": "TESTED"}),
        ]
        with self.assertRaisesRegex(ValueError, "illegal promotion jump"):
            replay(S0, events)

    def test_dependency_invalidation_is_replayable(self):
        events = [
            ev(1, "E1", "UPSERT_CLAIM", {"claim_id": "A", "claim": "A", "status": "UNKNOWN"}),
            ev(2, "E2", "UPSERT_CLAIM", {"claim_id": "B", "claim": "B", "status": "UNKNOWN", "dependencies": ["A"]}),
            ev(3, "E3", "SET_CLAIM_STATUS", {"claim_id": "B", "status": "HYPOTHESIS"}),
            ev(4, "E4", "INVALIDATE_DEPENDENTS", {"claim_id": "A", "status": "INDETERMINATE"}),
        ]
        state = replay(S0, events)
        self.assertEqual(state["claims"]["B"]["status"], "INDETERMINATE")
        self.assertEqual(state["claims"]["B"]["evidence_ids"], ["E2", "E3", "E4"])
        self.assertEqual(gate0(S0, events, state)["status"], "PASS")

    def test_materialized_state_corruption_detected(self):
        events = [ev(1, "E1", "SET_OBJECTIVE", {"objective": "x"})]
        state = replay(S0, events)
        corrupted = copy.deepcopy(state)
        corrupted["objective"] = "mutated"
        self.assertEqual(gate0(S0, events, corrupted)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
