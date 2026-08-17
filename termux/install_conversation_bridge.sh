#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

VERSION="1.0.0"
REPO_URL="${FROST_REPO_URL:-https://github.com/12ephods-source/centinal26.git}"
REPO_REF="${FROST_REPO_REF:-agent/conversation-termux-loop}"
ROOT="${FROST_CONVERSATION_WORKER_HOME:-$HOME/.frost_conversation_worker}"
SRC="$ROOT/centinal26"
VENV="$ROOT/venv"
NODE="$ROOT/node"
STATE="$ROOT/state"
LOGS="$ROOT/logs"
BIN="$HOME/.local/bin"
CFG="$ROOT/worker.env"
WORKER="$ROOT/base44_conversation_worker.mjs"
PIDFILE="$STATE/worker.pid"
LOGFILE="$LOGS/worker.log"
CAPS="$ROOT/capabilities"

say(){ printf '[frost-conversation] %s\n' "$*"; }
die(){ printf '[frost-conversation] ERROR: %s\n' "$*" >&2; exit 1; }
have(){ command -v "$1" >/dev/null 2>&1; }

[[ "${PREFIX:-}" == *com.termux* ]] || die "Run this installer inside Termux."
mkdir -p "$ROOT" "$STATE" "$LOGS" "$BIN" "$CAPS" "$NODE"
chmod 700 "$ROOT" "$STATE" "$LOGS" "$CAPS" "$NODE"

say "Checking runtimes"
missing=()
for cmd in python git node npm; do have "$cmd" || missing+=("$cmd"); done
if ((${#missing[@]})); then
  say "Missing: ${missing[*]}; attempting Termux package installation"
  have pkg || die "pkg is unavailable; install Python, Git, Node.js and npm first."
  pkg install -y python git nodejs-lts coreutils procps termux-api 2>/dev/null || \
    pkg install -y python git nodejs coreutils procps termux-api 2>/dev/null || true
fi
for cmd in python git node npm; do have "$cmd" || die "Required command still missing: $cmd"; done

say "Installing isolated Centinal26 source"
if [[ ! -d "$SRC/.git" ]]; then
  git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$SRC"
else
  git -C "$SRC" fetch --depth 1 origin "$REPO_REF"
  git -C "$SRC" checkout --detach FETCH_HEAD
fi
python -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check --no-input -e "$SRC" >/dev/null
"$VENV/bin/python" -c 'import frost_core.conversation_cli, frost_core.conversation_loop, frost_core.capability_executor' \
  || die "Centinal26 conversation modules failed to import."

say "Installing Base44 SDK"
cd "$NODE"
[[ -f package.json ]] || npm init -y >/dev/null 2>&1
npm install @base44/sdk >/dev/null
cp "$SRC/termux/base44_conversation_worker.mjs" "$WORKER"
chmod 600 "$WORKER"
node --check "$WORKER"

if [[ ! -f "$CFG" ]]; then
  say "First-run credentials. Values are stored only in $CFG (mode 600)."
  B44_EMAIL="${BASE44_WORKER_EMAIL:-${BASE44_EMAIL:-}}"
  B44_TOKEN="${BASE44_AUTH_TOKEN:-${BASE44_TOKEN:-}}"
  OPENAI_KEY="${OPENAI_API_KEY:-}"
  AI_MODEL="${FROST_AI_MODEL:-gpt-5.6}"
  if [[ -z "$B44_EMAIL" ]]; then
    printf 'Base44 worker email: '
    IFS= read -r B44_EMAIL
  fi
  if [[ -z "$B44_TOKEN" ]]; then
    printf 'Base44 user token: '
    IFS= read -rs B44_TOKEN
    printf '\n'
  fi
  if [[ -z "$OPENAI_KEY" ]]; then
    printf 'OpenAI API key for the responder: '
    IFS= read -rs OPENAI_KEY
    printf '\n'
  fi
  [[ -n "$B44_EMAIL" ]] || die "Base44 worker email is required."
  [[ -n "$B44_TOKEN" ]] || die "Base44 user token is required."
  [[ -n "$OPENAI_KEY" ]] || die "OpenAI API key is required for conversation.ingest."
  {
    printf 'BASE44_APP_ID=%q\n' '6a484dc22829dd2fd4a7bcd1'
    printf 'BASE44_WORKER_EMAIL=%q\n' "$B44_EMAIL"
    printf 'BASE44_AUTH_TOKEN=%q\n' "$B44_TOKEN"
    printf 'OPENAI_API_KEY=%q\n' "$OPENAI_KEY"
    printf 'FROST_AI_MODEL=%q\n' "$AI_MODEL"
    printf 'FROST_PYTHON=%q\n' "$VENV/bin/python"
    printf 'FROST_CONVERSATION_HOME=%q\n' "$ROOT/conversation"
    printf 'FROST_CONVERSATION_WORKER_HOME=%q\n' "$ROOT"
    printf 'FROST_BRIDGE_POLL_SECONDS=%q\n' '8'
    printf 'FROST_BRIDGE_HEARTBEAT_SECONDS=%q\n' '30'
    printf 'FROST_BRIDGE_LEASE_SECONDS=%q\n' '300'
  } > "$CFG"
  chmod 600 "$CFG"
else
  say "Preserving existing bridge credentials/config: $CFG"
fi

cat > "$CAPS/system_status.sh" <<'CAP'
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
printf 'timestamp_utc=%s\n' "$(date -u +%FT%TZ)"
printf 'android_release=%s\n' "$(getprop ro.build.version.release 2>/dev/null || true)"
printf 'android_sdk=%s\n' "$(getprop ro.build.version.sdk 2>/dev/null || true)"
printf 'device_model=%s\n' "$(getprop ro.product.model 2>/dev/null || true)"
printf 'kernel=%s\n' "$(uname -srmo 2>/dev/null || true)"
printf 'uptime=%s\n' "$(uptime 2>/dev/null || true)"
df -Pk "$HOME" 2>/dev/null | tail -n 1 | sed 's/^/home_df=/' || true
CAP
chmod 700 "$CAPS/system_status.sh"

cat > "$CAPS/centinal26_status.sh" <<CAP
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
exec "$VENV/bin/centinal26" status
CAP
chmod 700 "$CAPS/centinal26_status.sh"

export FROST_CONVERSATION_HOME="$ROOT/conversation"
"$VENV/bin/python" -m frost_core.conversation_cli register \
  --name termux.system_status \
  --script "$CAPS/system_status.sh" \
  --description "Read bounded Android/Termux system status. No arguments." \
  --max-args 0 --timeout 15 >/dev/null
"$VENV/bin/python" -m frost_core.conversation_cli register \
  --name centinal26.status \
  --script "$CAPS/centinal26_status.sh" \
  --description "Read Centinal26 local runtime status. No arguments." \
  --max-args 0 --timeout 30 >/dev/null

cat > "$BIN/frost-conversation-bridge-start" <<'START'
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
ROOT="${FROST_CONVERSATION_WORKER_HOME:-$HOME/.frost_conversation_worker}"
CFG="$ROOT/worker.env"
PIDFILE="$ROOT/state/worker.pid"
LOG="$ROOT/logs/worker.log"
[[ -f "$CFG" ]] || { echo "Missing $CFG" >&2; exit 1; }
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "RUNNING pid=$(cat "$PIDFILE")"
  exit 0
fi
set -a
# Generated by installer with shell-escaped literal values and mode 600.
source "$CFG"
set +a
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock || true
cd "$ROOT/node"
nohup node "$ROOT/base44_conversation_worker.mjs" >>"$LOG" 2>&1 &
printf '%s\n' "$!" > "$PIDFILE"
chmod 600 "$PIDFILE"
echo "STARTED pid=$(cat "$PIDFILE") log=$LOG"
START

cat > "$BIN/frost-conversation-bridge-stop" <<'STOP'
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
ROOT="${FROST_CONVERSATION_WORKER_HOME:-$HOME/.frost_conversation_worker}"
PIDFILE="$ROOT/state/worker.pid"
if [[ -f "$PIDFILE" ]]; then
  PID="$(cat "$PIDFILE")"
  kill "$PID" 2>/dev/null || true
  rm -f "$PIDFILE"
fi
command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock || true
echo STOPPED
STOP

cat > "$BIN/frost-conversation-bridge-status" <<'STATUS'
#!/data/data/com.termux/files/usr/bin/bash
ROOT="${FROST_CONVERSATION_WORKER_HOME:-$HOME/.frost_conversation_worker}"
PIDFILE="$ROOT/state/worker.pid"
LOG="$ROOT/logs/worker.log"
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "RUNNING pid=$(cat "$PIDFILE")"
else
  echo STOPPED
fi
[[ -f "$LOG" ]] && tail -n 40 "$LOG"
STATUS

cat > "$BIN/frost-conversation-register" <<REGISTER
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
export FROST_CONVERSATION_HOME="$ROOT/conversation"
exec "$VENV/bin/python" -m frost_core.conversation_cli register "\$@"
REGISTER

chmod 700 \
  "$BIN/frost-conversation-bridge-start" \
  "$BIN/frost-conversation-bridge-stop" \
  "$BIN/frost-conversation-bridge-status" \
  "$BIN/frost-conversation-register"

mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/frost_conversation_bridge.sh" <<BOOT
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$BIN:\$PATH"
"$BIN/frost-conversation-bridge-start" >> "$LOGS/boot.log" 2>&1 || true
BOOT
chmod 700 "$HOME/.termux/boot/frost_conversation_bridge.sh"

say "Running local status self-test"
printf '%s' '{"operation":"conversation.status"}' | \
  FROST_CONVERSATION_HOME="$ROOT/conversation" \
  "$VENV/bin/python" -m frost_core.conversation_cli | tee "$STATE/local_status.json"
"$VENV/bin/python" - "$STATE/local_status.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
assert x['ok'] is True
assert 'termux.system_status' in x['result']['registered_tools']
assert 'centinal26.status' in x['result']['registered_tools']
print('LOCAL_CONVERSATION_CORE=PASS')
PY

"$BIN/frost-conversation-bridge-stop" >/dev/null 2>&1 || true
"$BIN/frost-conversation-bridge-start"
sleep 2
"$BIN/frost-conversation-bridge-status" || true

say "Installed. Persistent worker now polls Base44 for conversation.ingest/status jobs."
say "AI tool execution is limited to locally registered, SHA-256-pinned scripts."
say "Register another local capability with: frost-conversation-register --name NAME --script PATH --description TEXT"
say "Termux:Boot launcher installed at ~/.termux/boot/frost_conversation_bridge.sh"
