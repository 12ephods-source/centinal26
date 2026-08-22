#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="${CENTINAL26_HOME:-$HOME/.centinal26}"
"$ROOT/bin/centinal26_daemon_service.sh" start >/dev/null
python "$ROOT/bin/centinal26_improvement_cycle.py"
