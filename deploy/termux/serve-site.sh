#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

REPO_DIR="${1:-$HOME/centinal26}"
PORT="${PORT:-8080}"
BIND="${BIND:-127.0.0.1}"

if ! command -v python >/dev/null 2>&1; then
  pkg install -y python
fi

if [ ! -f "$REPO_DIR/site/serve.py" ]; then
  printf 'ERROR: %s/site/serve.py not found\n' "$REPO_DIR" >&2
  printf 'Clone or update the repository first, then rerun.\n' >&2
  exit 2
fi

cd "$REPO_DIR"
printf 'Starting Automation OS website from %s/site\n' "$REPO_DIR"
exec python site/serve.py --bind "$BIND" --port "$PORT"
