#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

APP_ID="6a484dc22829dd2fd4a7bcd1"
ROOT="${AUTOMATION_BRIDGE_ROOT:-$HOME/.automation_bridge}"
STATE_ROOT="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
CFG="$ROOT/bridge.env"
STATE="$ROOT/state"
LOGS="$ROOT/logs"
BIN="$ROOT/bin"
WORKER="$ROOT/fleet_worker.mjs"
PIDFILE="$STATE/fleet_worker.pid"
INSTANCE_FILE="$STATE_ROOT/device-identity.json"
DEFAULT_EMAIL="${FROST_BASE44_WORKER_EMAIL:-12ephods@gmail.com}"

say(){ printf '[frost-base44] %s\n' "$*"; }
die(){ printf '[frost-base44] ERROR: %s\n' "$*" >&2; exit 1; }

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) die "Run this inside Termux on an Android phone." ;;
esac
command -v pkg >/dev/null 2>&1 || die "Termux pkg is unavailable."

missing=()
command -v node >/dev/null 2>&1 || missing+=(nodejs-lts)
command -v npm >/dev/null 2>&1 || missing+=(nodejs-lts)
command -v openssl >/dev/null 2>&1 || missing+=(openssl)
command -v pgrep >/dev/null 2>&1 || missing+=(procps)
command -v sha256sum >/dev/null 2>&1 || missing+=(coreutils)
if ((${#missing[@]})); then
  say "Installing missing worker runtime packages: ${missing[*]}"
  if ! pkg install -y "${missing[@]}"; then
    retry=()
    for p in "${missing[@]}"; do
      [[ "$p" == nodejs-lts ]] && retry+=(nodejs) || retry+=("$p")
    done
    pkg install -y "${retry[@]}" || die "Worker runtime provisioning failed."
  fi
fi
for c in node npm openssl pgrep sha256sum; do
  command -v "$c" >/dev/null 2>&1 || die "Required worker command unavailable: $c"
done

mkdir -p "$ROOT" "$STATE" "$LOGS" "$BIN" "$STATE_ROOT" "$HOME/.local/bin" "$HOME/.termux/boot"
chmod 700 "$ROOT" "$STATE" "$LOGS" "$BIN" "$STATE_ROOT" "$HOME/.termux/boot" 2>/dev/null || true

say "Ensuring Base44 SDK."
cd "$ROOT"
[[ -f package.json ]] || npm init -y >/dev/null 2>&1
if ! node -e "import('@base44/sdk').then(()=>process.exit(0)).catch(()=>process.exit(1))" >/dev/null 2>&1; then
  npm install @base44/sdk
fi
node -e "import('@base44/sdk').then(()=>process.exit(0)).catch(()=>process.exit(1))" || die "Base44 SDK import failed."

if [[ -s "$INSTANCE_FILE" ]]; then
  DEVICE_ID="$(node -e 'const fs=require("fs");const p=process.argv[1];const v=JSON.parse(fs.readFileSync(p,"utf8"));if(v.schema!=="centinal26-device-identity-v1"||!v.device_id)process.exit(2);process.stdout.write(String(v.device_id));' "$INSTANCE_FILE")" || die "Persisted Centinal26 device identity is invalid."
else
  uuid="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || true)"
  [[ -n "$uuid" ]] || uuid="$(openssl rand -hex 16)"
  DEVICE_ID="android-$(uname -m)-$uuid"
  printf '{"schema":"centinal26-device-identity-v1","device_id":"%s"}\n' "$DEVICE_ID" > "$INSTANCE_FILE"
  chmod 600 "$INSTANCE_FILE"
fi
export AUTOMATION_DEVICE_ID="$DEVICE_ID"
say "Execution identity: $DEVICE_ID"

if [[ ! -f "$CFG" ]]; then
  if [[ -n "${BASE44_TOKEN:-}" && -n "${BASE44_WORKER_EMAIL:-${BASE44_EMAIL:-}}" ]]; then
    email="${BASE44_WORKER_EMAIL:-${BASE44_EMAIL}}"
    {
      printf 'BASE44_APP_ID=%q\n' "$APP_ID"
      printf 'BASE44_WORKER_EMAIL=%q\n' "$email"
      printf 'BASE44_TOKEN=%q\n' "$BASE44_TOKEN"
      printf 'POLL_SECONDS=%q\n' "8"
    } > "$CFG"
  elif [[ -n "${BASE44_PASSWORD:-}" && -n "${BASE44_EMAIL:-}" ]]; then
    {
      printf 'BASE44_APP_ID=%q\n' "$APP_ID"
      printf 'BASE44_EMAIL=%q\n' "$BASE44_EMAIL"
      printf 'BASE44_PASSWORD=%q\n' "$BASE44_PASSWORD"
      printf 'POLL_SECONDS=%q\n' "8"
    } > "$CFG"
  elif [[ -t 0 ]]; then
    printf 'Base44 worker email [%s]: ' "$DEFAULT_EMAIL"
    IFS= read -r email
    email="${email:-$DEFAULT_EMAIL}"
    printf 'Authentication mode [token/password] (default token): '
    IFS= read -r mode
    mode="${mode:-token}"
    case "$mode" in
      token)
        printf 'Base44 token: '
        IFS= read -rs secret
        printf '\n'
        [[ -n "$secret" ]] || die "Token is required."
        {
          printf 'BASE44_APP_ID=%q\n' "$APP_ID"
          printf 'BASE44_WORKER_EMAIL=%q\n' "$email"
          printf 'BASE44_TOKEN=%q\n' "$secret"
          printf 'POLL_SECONDS=%q\n' "8"
        } > "$CFG"
        ;;
      password)
        printf 'Base44 password: '
        IFS= read -rs secret
        printf '\n'
        [[ -n "$secret" ]] || die "Password is required."
        {
          printf 'BASE44_APP_ID=%q\n' "$APP_ID"
          printf 'BASE44_EMAIL=%q\n' "$email"
          printf 'BASE44_PASSWORD=%q\n' "$secret"
          printf 'POLL_SECONDS=%q\n' "8"
        } > "$CFG"
        ;;
      *) die "Authentication mode must be token or password." ;;
    esac
  else
    say "AUTH_REQUIRED: set BASE44_TOKEN + BASE44_WORKER_EMAIL, or BASE44_EMAIL + BASE44_PASSWORD, then rerun."
    exit 20
  fi
fi
chmod 600 "$CFG"

cat > "$WORKER" <<'NODE'
import { createClient } from "@base44/sdk";
import { readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const VERSION = "centinal26-base44-fleet-worker/1.0.0";
const PROTOCOL = "frost-call/1.0";
const ROOT = process.env.AUTOMATION_BRIDGE_ROOT || path.join(os.homedir(), ".automation_bridge");
const STATE_ROOT = process.env.CENTINAL26_HOME || path.join(os.homedir(), ".local/state/centinal26");
const APP_ID = process.env.BASE44_APP_ID || "6a484dc22829dd2fd4a7bcd1";
const EMAIL = process.env.BASE44_WORKER_EMAIL || process.env.BASE44_EMAIL || "";
const TOKEN = process.env.BASE44_TOKEN || "";
const PASSWORD = process.env.BASE44_PASSWORD || "";
const POLL_MS = Math.max(5000, Number(process.env.POLL_SECONDS || 8) * 1000);
const HEARTBEAT_MS = 60_000;
const ALLOWED = new Set(["system.health", "system.capabilities"]);
const identity = JSON.parse(await readFile(path.join(STATE_ROOT, "device-identity.json"), "utf8"));
const instanceId = String(identity.device_id || "");
const bootId = (await readFile("/proc/sys/kernel/random/boot_id", "utf8").catch(()=>"unknown\n")).trim();
const startedAt = new Date().toISOString();

function now(){ return new Date().toISOString(); }
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
function allowed(op){ return ALLOWED.has(String(op || "")); }
if (process.argv.includes("--self-test")) {
  const checks = [
    ["allow-health", allowed("system.health")],
    ["allow-capabilities", allowed("system.capabilities")],
    ["deny-shell", !allowed("shell.exec")],
    ["deny-workflow", !allowed("workflow.execute")],
    ["deny-install", !allowed("capability.ensure")],
  ];
  for (const [name, ok] of checks) console.log(`${ok ? "PASS" : "FAIL"} ${name}`);
  process.exit(checks.every(([,ok])=>ok) ? 0 : 1);
}
if (!EMAIL || (!TOKEN && !PASSWORD) || !instanceId) process.exit(2);
let b;
if (TOKEN) b = createClient({appId:APP_ID, token:TOKEN});
else { b = createClient({appId:APP_ID}); await b.auth.loginViaEmailPassword(EMAIL, PASSWORD); }
let workerRowId = "";
async function upsertWorker(status="online", extra={}) {
  const data = {
    worker_email: EMAIL, instance_id: instanceId, status, last_seen: now(), version: VERSION,
    capabilities_json: JSON.stringify({role:"capability-routed-fleet-executor", arbitrary_shell:false, boot_id:bootId, process_started_at:startedAt, ...extra}),
    protocol_versions_json: JSON.stringify([PROTOCOL]), supported_operations_json: JSON.stringify([...ALLOWED]),
    platform:"android/termux", runtime:`node/${process.version}`, boot_id:bootId, max_concurrency:1,
    promotion_stage:"HOST_VALIDATED", supervisor_status:"running"
  };
  if (!workerRowId) {
    const rows = await b.entities.AutomationWorker.filter({worker_email:EMAIL, instance_id:instanceId}, "-updated_date", 1, 0).catch(()=>[]);
    workerRowId = rows?.[0]?.id || "";
  }
  if (workerRowId) await b.entities.AutomationWorker.update(workerRowId, data);
  else { const row = await b.entities.AutomationWorker.create(data); workerRowId = row?.id || ""; }
}
async function execute(job) {
  const op = String(job.operation || "");
  if (!allowed(op)) return false;
  const claimed = now();
  await b.entities.AutomationJob.update(job.id, {status:"claimed", worker_instance_id:instanceId, claimed_at:claimed, heartbeat_at:claimed, lease_until:new Date(Date.now()+300000).toISOString(), attempt:Number(job.attempt||0)+1});
  await b.entities.AutomationJob.update(job.id, {status:"running", started_at:now(), heartbeat_at:now()});
  const result = op === "system.health" ? {
    status:"healthy", platform:"android/termux", worker_instance_id:instanceId, boot_id:bootId,
    component:VERSION, protocol:PROTOCOL, arbitrary_shell:false, probe_executed_at:now()
  } : {
    platform:"android/termux", worker_instance_id:instanceId, boot_id:bootId, protocol_versions:[PROTOCOL],
    operations:[...ALLOWED], arbitrary_shell:false, capability_routing:true
  };
  const done = now();
  await b.entities.AutomationJob.update(job.id, {status:"completed", finished_at:done, heartbeat_at:done, lease_until:done, result_summary:JSON.stringify(result), error_message:""});
  await upsertWorker("online", {last_operation:op, last_job_id:job.id});
  return true;
}
console.log(`[${VERSION}] email=${EMAIL} instance=${instanceId} boot_id=${bootId}`);
await upsertWorker("online", {startup:true});
let lastHeartbeat = Date.now();
while (true) {
  try {
    const jobs = await b.entities.AutomationJob.filter({status:"queued", worker_email:EMAIL, job_type:"frost_call"}, "-priority", 20, 0);
    for (const job of jobs || []) {
      const op = String(job.operation || "");
      if (!allowed(op)) continue;
      try { await execute(job); } catch (e) { console.error(`[job-fail] ${job.id}`, e?.stack || e); }
    }
    if (Date.now() - lastHeartbeat >= HEARTBEAT_MS) { await upsertWorker("online"); lastHeartbeat = Date.now(); }
  } catch (e) { console.error(`[cycle-error ${now()}]`, e?.stack || e); }
  await sleep(POLL_MS);
}
NODE
chmod 600 "$WORKER"

cat > "$BIN/fleet-worker-start" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
ROOT="${AUTOMATION_BRIDGE_ROOT:-$HOME/.automation_bridge}"
CFG="$ROOT/bridge.env"
PIDFILE="$ROOT/state/fleet_worker.pid"
LOG="$ROOT/logs/fleet_worker.log"
[[ -f "$CFG" ]] || { echo "Missing $CFG" >&2; exit 1; }
if [[ -f "$PIDFILE" ]]; then
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then echo "fleet worker already running: PID $pid"; exit 0; fi
  rm -f "$PIDFILE"
fi
set -a
# shellcheck disable=SC1090
source "$CFG"
set +a
nohup node "$ROOT/fleet_worker.mjs" >> "$LOG" 2>&1 </dev/null &
echo $! > "$PIDFILE"
chmod 600 "$PIDFILE"
sleep 1
pid="$(cat "$PIDFILE")"
kill -0 "$pid" 2>/dev/null || { echo "fleet worker failed; inspect $LOG" >&2; exit 1; }
echo "fleet worker started: PID $pid"
SH

cat > "$BIN/fleet-worker-stop" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
ROOT="${AUTOMATION_BRIDGE_ROOT:-$HOME/.automation_bridge}"
PIDFILE="$ROOT/state/fleet_worker.pid"
if [[ -f "$PIDFILE" ]]; then
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  rm -f "$PIDFILE"
fi
echo "fleet worker stopped"
SH

cat > "$BIN/fleet-worker-status" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
ROOT="${AUTOMATION_BRIDGE_ROOT:-$HOME/.automation_bridge}"
PIDFILE="$ROOT/state/fleet_worker.pid"
LOG="$ROOT/logs/fleet_worker.log"
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then echo "RUNNING pid=$(cat "$PIDFILE")"; else echo "STOPPED"; fi
tail -n 30 "$LOG" 2>/dev/null || true
SH
chmod 700 "$BIN/fleet-worker-start" "$BIN/fleet-worker-stop" "$BIN/fleet-worker-status"
ln -sf "$BIN/fleet-worker-start" "$HOME/.local/bin/frost-fleet-worker-start"
ln -sf "$BIN/fleet-worker-stop" "$HOME/.local/bin/frost-fleet-worker-stop"
ln -sf "$BIN/fleet-worker-status" "$HOME/.local/bin/frost-fleet-worker-status"

cat > "$HOME/.termux/boot/start-frost-fleet-worker.sh" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
sleep 20
"$HOME/.local/bin/frost-fleet-worker-start" >/dev/null 2>&1 || true
SH
chmod 700 "$HOME/.termux/boot/start-frost-fleet-worker.sh"

set -a
# shellcheck disable=SC1090
source "$CFG"
set +a
node --check "$WORKER"
node "$WORKER" --self-test
"$BIN/fleet-worker-stop" >/dev/null 2>&1 || true
"$BIN/fleet-worker-start"
say "Base44 fleet worker installed. Status: frost-fleet-worker-status"
say "Only system.health and system.capabilities are remotely executable at bootstrap stage."
say "Conversation/job routing remains capability-based; device identity is provenance only."
