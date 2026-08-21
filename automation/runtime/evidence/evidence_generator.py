"""Execution evidence generator scaffold.

Creates structured evidence records for runtime tasks.
Evidence generation does not prove correctness; validation remains separate.
"""

from datetime import datetime, timezone
import json
import hashlib


def create_evidence(request, result=None, verification=None):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request": request,
        "result": result,
        "verification": verification,
        "status": "PENDING_VERIFICATION"
    }
    return record


def hash_record(record):
    payload = json.dumps(record, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
