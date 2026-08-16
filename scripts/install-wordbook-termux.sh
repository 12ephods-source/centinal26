#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${WORDBOOK_HOME:-$HOME/.local/state/centinal26/wordbook}"
DB="$STATE_DIR/wordbook.sqlite3"
REPORT="$STATE_DIR/WORD_BOOK_DEVICE_VALIDATION_REPORT.json"
REPORT_SHA="$REPORT.sha256"
IMPORT_REPORT="$STATE_DIR/LAST_CHATGPT_IMPORT.json"
EXPORT_PATH="${1:-}"

fail() {
  printf 'wordbook-termux: %s\n' "$*" >&2
  exit 2
}

case "${PREFIX:-}" in
  /data/data/com.termux/files/usr*) ;;
  *) fail "this validation gate must be executed inside Termux" ;;
esac

command -v python >/dev/null 2>&1 || fail "python is required"
python - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Wordbook requires Python 3.11+")
PY

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
python -m pip install -e "$ROOT"
command -v centinal26-wordbook >/dev/null 2>&1 || fail "centinal26-wordbook CLI was not installed"
command -v centinal26-wordbook-archive >/dev/null 2>&1 || fail "archive CLI was not installed"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/conversations.json" <<'JSON'
[
  {
    "id": "wordbook-device-selftest",
    "mapping": {
      "u1": {
        "message": {
          "id": "u1",
          "author": {"role": "user"},
          "content": {"parts": ["I don't say basically."]}
        }
      },
      "u2": {
        "message": {
          "id": "u2",
          "author": {"role": "user"},
          "content": {"parts": ["Proceed. Proceed."]}
        }
      },
      "a1": {
        "message": {
          "id": "a1",
          "author": {"role": "assistant"},
          "content": {"parts": ["Basically, this assistant text must not become user evidence."]}
        }
      }
    }
  }
]
JSON

ROOT="$ROOT" TMP="$TMP" REPORT="$REPORT" python - <<'PY'
from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from centinal26.wordbook import WordbookStore
from centinal26.wordbook_archive import ingest_chatgpt_zip

root = Path(os.environ["ROOT"])
tmp = Path(os.environ["TMP"])
report_path = Path(os.environ["REPORT"])
db_path = tmp / "selftest.sqlite3"
archive_path = tmp / "chatgpt-export-selftest.zip"

with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(tmp / "conversations.json", arcname="conversations.json")
    archive.writestr("user.json", "{}")

checks: dict[str, object] = {}
with WordbookStore(db_path) as store:
    archive_report = ingest_chatgpt_zip(store, archive_path)
    basically = store.query("basically")
    proceed = store.query("proceed")
    evolution = store.evolve()
    checks["archive_import_recorded"] = archive_report.ledger_recorded
    checks["archive_sha256_present"] = len(archive_report.archive_sha256) == 64
    checks["user_messages"] = archive_report.user_messages == 2
    checks["non_user_messages_excluded"] = archive_report.non_user_messages == 1
    checks["meta_not_ordinary"] = (
        basically.ordinary_usage == 0 and basically.meta_reference == 1
    )
    checks["direct_count_exact"] = proceed.ordinary_usage == 2
    checks["evolution_exactly_100"] = (
        evolution.generations == 100 and len(evolution.records) == 100
    )
    checks["evidence_pinned"] = len(
        {record.evidence_sha256 for record in evolution.records}
    ) == 1
    corpus_sha256 = store.corpus_digest()

fts5_enabled = bool(
    sqlite3.connect(":memory:")
    .execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')")
    .fetchone()[0]
)
checks["sqlite_available"] = True
checks["all_required"] = all(bool(value) for value in checks.values())

report = {
    "schema": "wordbook-termux-device-validation-v2",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "status": "TERMUX_SELFTEST_PASS" if checks["all_required"] else "TERMUX_SELFTEST_FAIL",
    "promotion_authorized": False,
    "repository_root": str(root),
    "environment": {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "fts5_enabled": fts5_enabled,
        "termux_version": os.environ.get("TERMUX_VERSION"),
        "prefix": os.environ.get("PREFIX"),
    },
    "checks": checks,
    "synthetic_archive_sha256": archive_report.archive_sha256,
    "synthetic_conversations_sha256": archive_report.conversations_sha256,
    "synthetic_corpus_sha256": corpus_sha256,
    "notes": [
        "Synthetic ZIP and validation database are isolated from the persistent Wordbook database.",
        "TERMUX_SELFTEST_PASS is physical execution evidence, not permission to promote the module.",
        "FTS5 is optional; exact count functionality does not depend on it.",
    ],
}
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
report_path.chmod(0o600)
if not checks["all_required"]:
    raise SystemExit(1)
PY

REPORT="$REPORT" REPORT_SHA="$REPORT_SHA" python - <<'PY'
import hashlib
import os
from pathlib import Path

report = Path(os.environ["REPORT"])
out = Path(os.environ["REPORT_SHA"])
digest = hashlib.sha256(report.read_bytes()).hexdigest()
out.write_text(f"{digest}  {report.name}\n", encoding="utf-8")
out.chmod(0o600)
print(f"device_report={report}")
print(f"device_report_sha256={digest}")
PY

if [[ -n "$EXPORT_PATH" ]]; then
  [[ -f "$EXPORT_PATH" ]] || fail "ChatGPT export not found: $EXPORT_PATH"
  case "$EXPORT_PATH" in
    *.zip|*.ZIP)
      centinal26-wordbook-archive \
        --db "$DB" \
        --report "$IMPORT_REPORT" \
        "$EXPORT_PATH"
      ;;
    *.json|*.JSON)
      centinal26-wordbook --db "$DB" ingest-chatgpt "$EXPORT_PATH"
      ;;
    *)
      fail "expected a ChatGPT export ZIP or conversations.json"
      ;;
  esac
  chmod 600 "$DB" 2>/dev/null || true
  printf 'persistent_db=%s\n' "$DB"
else
  printf '%s\n' "No personal corpus imported. Pass the ChatGPT export ZIP or conversations.json as the first argument after device validation."
fi

printf '%s\n' "Wordbook Termux validation gate completed. Promotion remains explicit."
