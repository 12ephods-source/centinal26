#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
FROST_ROOT="${FROST_ROOT:-$HOME/frost}"
REPO="${CENTINAL26_ROOT:-$FROST_ROOT/centinal26}"
HOST="${OPENQUEST_HOST:-127.0.0.1}"
PORT="${OPENQUEST_PORT:-8765}"
[ -d "$REPO/.git" ] || { echo "Centinal26 not installed at $REPO" >&2; exit 2; }
cd "$REPO"
if command -v frost-autopilot-update >/dev/null 2>&1; then
  frost-autopilot-update --project centinal26 --install-python || echo "Update blocked or failed; preserving current checkout." >&2
fi
python -m unittest discover -s openquest/tests -q
printf 'OpenQuestRPG: http://%s:%s/\n' "$HOST" "$PORT"
exec python -m openquest.service --host "$HOST" --port "$PORT"
