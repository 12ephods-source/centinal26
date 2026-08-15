#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="${CENTINAL26_REPO_URL:-https://github.com/12ephods-source/centinal26.git}"
INSTALL_ROOT="${CENTINAL26_INSTALL_ROOT:-$HOME/centinal26}"
STATE_ROOT="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"

pkg update -y
pkg install -y python git

if [ -d "$INSTALL_ROOT/.git" ]; then
  git -C "$INSTALL_ROOT" fetch --all --prune
  git -C "$INSTALL_ROOT" pull --ff-only
else
  git clone "$REPO_URL" "$INSTALL_ROOT"
fi

cd "$INSTALL_ROOT"
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

export CENTINAL26_HOME="$STATE_ROOT"
export CENTINAL26_TIMEZONE="${CENTINAL26_TIMEZONE:-America/Mexico_City}"
mkdir -p "$CENTINAL26_HOME"
centinal26-intelligence init

cat <<EOF
Automation Intelligence Controller installed.

State: $CENTINAL26_HOME/intelligence.sqlite3
Run one control cycle:
  cd "$INSTALL_ROOT" && . .venv/bin/activate && centinal26-intelligence cycle

Run the persistent local controller:
  cd "$INSTALL_ROOT" && . .venv/bin/activate && centinal26-intelligence daemon --poll 10

Termux:Boot is intentionally not enabled by this installer. Prove normal device execution,
heartbeats, job claiming/completion, and recovery first; then persistence can be promoted
through the existing physical-device gates.
EOF
