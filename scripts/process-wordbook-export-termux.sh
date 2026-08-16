#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${WORDBOOK_HOME:-$HOME/.local/state/centinal26/wordbook}"
EVIDENCE_ROOT="${CENTINAL26_EXPORT_EVIDENCE_ROOT:-$HOME/.local/share/centinal26/evidence/exports}"
DB="$STATE_DIR/wordbook.sqlite3"
REPORT="$STATE_DIR/LAST_CORPUS_BUILD.json"
DICTIONARY="$STATE_DIR/WORD_BOOK_DICTIONARY.json"

fail() {
  printf 'wordbook-consumer: %s\n' "$*" >&2
  exit 2
}

case "${PREFIX:-}" in
  /data/data/com.termux/files/usr*) ;;
  *) fail "must run inside Termux" ;;
esac

command -v python >/dev/null 2>&1 || fail "python is required"
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
python -m pip install -e "$ROOT" >/dev/null
command -v centinal26-wordbook-pipeline >/dev/null 2>&1 || fail "pipeline CLI unavailable"

if [[ "${1:-}" == "--receipt" ]]; then
  [[ -n "${2:-}" ]] || fail "--receipt requires a receipt ID"
  exec centinal26-wordbook-pipeline receipt "$2" \
    --evidence-root "$EVIDENCE_ROOT" \
    --db "$DB" \
    --state-dir "$STATE_DIR" \
    --report "$REPORT"
fi

if [[ -n "${1:-}" ]]; then
  [[ -f "$1" ]] || fail "export file not found: $1"
  exec centinal26-wordbook-pipeline source "$1" \
    --provider openai \
    --evidence-root "$EVIDENCE_ROOT" \
    --db "$DB" \
    --state-dir "$STATE_DIR" \
    --report "$REPORT"
fi

PRECHECK="$({
  STATE_DIR="$STATE_DIR" REPORT="$REPORT" DICTIONARY="$DICTIONARY" python - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

from centinal26.wordbook_archive import sha256_file
from centinal26.wordbook_pipeline import DEFAULT_DOWNLOAD_DIRS, discover_latest_export

try:
    source = discover_latest_export(list(DEFAULT_DOWNLOAD_DIRS))
except FileNotFoundError:
    print(json.dumps({"status": "NO_LOCAL_EXPORT"}, sort_keys=True))
    raise SystemExit(3)

sha256 = sha256_file(source)
report_path = Path(os.environ["REPORT"])
dictionary_path = Path(os.environ["DICTIONARY"])
state = {"status": "PROCESS", "source": str(source), "sha256": sha256}
if report_path.is_file() and dictionary_path.is_file():
    try:
        prior = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        prior = {}
    if prior.get("raw_sha256") == sha256:
        state["status"] = "UNCHANGED_ALREADY_DERIVED"
print(json.dumps(state, sort_keys=True))
PY
} 2>/dev/null)" || precheck_rc=$?
precheck_rc="${precheck_rc:-0}"
printf '%s\n' "$PRECHECK"

case "$precheck_rc" in
  0) ;;
  3) exit 0 ;;
  *) fail "local export discovery failed" ;;
esac

if [[ "$PRECHECK" == *'"status": "UNCHANGED_ALREADY_DERIVED"'* ]]; then
  exit 0
fi

exec centinal26-wordbook-pipeline latest \
  --provider openai \
  --evidence-root "$EVIDENCE_ROOT" \
  --db "$DB" \
  --state-dir "$STATE_DIR" \
  --report "$REPORT"
