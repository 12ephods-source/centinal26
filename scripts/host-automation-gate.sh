#!/usr/bin/env bash
set -Eeuo pipefail

: "${CENTINAL26_HOME:=$(mktemp -d)}"
export CENTINAL26_HOME

for _ in $(seq 1 10); do
  centinal26 auto-demo >/dev/null
done
centinal26 auto-selftest >/dev/null
status="$(centinal26 auto-status)"
printf '%s\n' "$status"
python - "$status" <<'PY'
import json
import sys

status = json.loads(sys.argv[1])
evolution = status["evolution"]
assert status["audit_valid"] is True
assert evolution["ready"] is True
assert evolution["consecutive_passes"] >= evolution["minimum_consecutive_passes"]
assert evolution["zero_state_divergence"] is True
assert evolution["evidence_complete"] is True
assert evolution["recovery_pass"] is True
assert evolution["verifier_independent"] is True
PY
