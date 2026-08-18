"""AREOP v1.0 fail-closed transition gates."""

CLAIM_STATES = {
    "UNKNOWN",
    "HYPOTHESIS",
    "DERIVED",
    "TESTED",
    "CORROBORATED",
    "CANONICAL",
    "FALSIFIED",
    "INDETERMINATE",
    "SUPERSEDED",
}

PROMOTION_ORDER = [
    "UNKNOWN",
    "HYPOTHESIS",
    "DERIVED",
    "TESTED",
    "CORROBORATED",
    "CANONICAL",
]


def validate_event(event, expected_seq):
    required = {"event_id", "seq", "kind", "payload"}
    missing = required - set(event)
    if missing:
        raise ValueError(f"missing event fields: {sorted(missing)}")
    seq = event["seq"]
    if not isinstance(seq, int) or isinstance(seq, bool):
        raise TypeError("seq must be an integer")
    if seq != expected_seq:
        raise ValueError(f"sequence mismatch: expected {expected_seq}, got {seq}")
    if not isinstance(event["event_id"], str) or not event["event_id"].strip():
        raise ValueError("event_id must be a non-empty string")
    if not isinstance(event["payload"], dict):
        raise TypeError("payload must be an object")


def validate_claim_status(status):
    if status not in CLAIM_STATES:
        raise ValueError(f"unknown claim status: {status}")


def validate_claim_status_transition(old_status, new_status):
    validate_claim_status(old_status)
    validate_claim_status(new_status)
    if old_status == new_status:
        return
    if old_status in {"FALSIFIED", "SUPERSEDED"} and new_status not in {"SUPERSEDED"}:
        raise ValueError(f"illegal transition from terminal claim status {old_status}")
    if (
        old_status in PROMOTION_ORDER
        and new_status in PROMOTION_ORDER
        and PROMOTION_ORDER.index(new_status) > PROMOTION_ORDER.index(old_status) + 1
    ):
        raise ValueError(f"illegal promotion jump: {old_status} -> {new_status}")


def hard_action_gate(action):
    for field in ("authorized", "safe", "traceable"):
        if action.get(field) is not True:
            return False
    return True
