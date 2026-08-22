#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

APP="$HOME/.local/share/frost-library-cleaner"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
WATCH_PID="$APP/action-watch.pid"
DASH_PID="$APP/autopilot-dashboard.pid"

mkdir -p "$APP"
install -m 0644 "$SOURCE_DIR/autopilot_cycle.py" "$APP/autopilot_cycle.py"
install -m 0644 "$SOURCE_DIR/action_watch.py" "$APP/action_watch.py"
install -m 0644 "$SOURCE_DIR/autopilot_dashboard.py" "$APP/autopilot_dashboard.py"
install -m 0644 "$SOURCE_DIR/physical_resume.py" "$APP/physical_resume.py"
python -m py_compile \
  "$APP/autopilot_cycle.py" \
  "$APP/action_watch.py" \
  "$APP/autopilot_dashboard.py" \
  "$APP/physical_resume.py"

start_once() {
  local pidfile="$1"
  shift
  if [ -f "$pidfile" ]; then
    local oldpid
    oldpid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "$oldpid" ] && kill -0 "$oldpid" 2>/dev/null; then
      return 0
    fi
  fi
  nohup "$@" >/dev/null 2>&1 &
  echo $! > "$pidfile"
}

echo "Installed Frost Forge autopilot + Centinal26 strict action watch."
echo "Priming action-watch evidence state."
python "$APP/action_watch.py" --json || rc=$?
rc="${rc:-0}"
if [ "$rc" -ne 0 ] && [ "$rc" -ne 2 ]; then
  echo "Action watch priming failed with rc=$rc" >&2
  exit "$rc"
fi

# Reuse the established physical-boundary solution automatically when this
# installer is actually running on Android/Termux. The helper is fail-closed:
# it preserves the device package but never claims controller verification or
# DEVICE_VALIDATED promotion.
echo "Evaluating canonical physical-device resume gate."
python "$APP/physical_resume.py" || physical_rc=$?
physical_rc="${physical_rc:-0}"
if [ "$physical_rc" -ne 0 ] && [ "$physical_rc" -ne 2 ]; then
  echo "Physical resume is degraded; preserving blocker and continuing independent work (rc=$physical_rc)." >&2
fi

start_once "$WATCH_PID" python "$APP/action_watch.py" --loop --interval 3600
start_once "$DASH_PID" python "$APP/autopilot_dashboard.py"

echo "Hourly strict action watch started."
echo "Autopilot dashboard: http://127.0.0.1:8765"
echo "Running bounded improvement loop (maximum 3 cycles)."
python "$APP/autopilot_cycle.py" autopilot --cycles 3
