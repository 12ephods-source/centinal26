#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077
ROOT="${CENTINAL26_HOME:-$HOME/.centinal26}"
PID="$ROOT/state/daemon.pid"
LOG="$ROOT/logs/supervisor.log"
DAEMON="$ROOT/bin/centinal26_daemon.py"
mkdir -p "$ROOT/state" "$ROOT/logs"

alive() { [[ -f "$PID" ]] && kill -0 "$(cat "$PID" 2>/dev/null)" 2>/dev/null; }
start() {
  if alive; then echo "already-running pid=$(cat "$PID")"; return 0; fi
  rm -f "$ROOT/state/STOP"
  nohup python "$DAEMON" >>"$LOG" 2>&1 &
  echo $! >"$PID"
  sleep 1
  if ! alive; then echo "daemon failed to start" >&2; return 1; fi
  echo "started pid=$(cat "$PID")"
}
stop() {
  touch "$ROOT/state/STOP"
  if alive; then
    kill "$(cat "$PID")" 2>/dev/null || true
    for _ in 1 2 3 4 5; do alive || break; sleep 1; done
  fi
  rm -f "$PID"
  echo stopped
}
status() {
  if alive; then echo "running pid=$(cat "$PID")"; else echo stopped; return 1; fi
  python "$ROOT/bin/centinal26ctl.py" status --limit 5 || true
}
case "${1:-start}" in start) start;; stop) stop;; restart) stop; start;; status) status;; *) echo "usage: $0 {start|stop|restart|status}" >&2; exit 2;; esac
