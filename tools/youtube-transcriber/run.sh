#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$APP_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$APP_DIR/.env"
  set +a
fi
exec python "$APP_DIR/transcribe.py" "$@"
