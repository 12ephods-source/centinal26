"""Execution evidence generator scaffold.

Creates structured evidence records for runtime tasks.
Evidence generation does not prove correctness; validation remains separate.
"""

import hashlib
import json
from datetime import UTC, datetime


def create_evidence(request, result=None, verification=None):
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "request": request,
        "result": result,
        "verification": verification,
        "status": "PENDING_VERIFICATION",
    }


def hash_record(record):
    payload = json.dumps(record, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
