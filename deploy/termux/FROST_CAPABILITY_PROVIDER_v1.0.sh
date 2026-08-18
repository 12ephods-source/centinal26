#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

ROOT="${AUTOMATION_BRIDGE_ROOT:-$HOME/.automation_bridge}"
STATE_ROOT="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
CFG="$ROOT/bridge.env"
BIN="$ROOT/bin"
WORKER="$ROOT/fleet_worker.mjs"
PROVIDER="$BIN/capability-ensure"
PIDFILE="$ROOT/state/fleet_worker.pid"
LOG="$ROOT/logs/fleet_worker.log"

say(){ printf '[frost-capability] %s\n' "$*"; }
die(){ printf '[frost-capability] ERROR: %s\n' "$*" >&2; exit 1; }

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) die "Run this inside Termux on Android." ;;
esac
command -v pkg >/dev/null 2>&1 || die "Termux pkg is unavailable."
[[ -f "$CFG" ]] || die "Base44 bridge authentication/config is not established: $CFG"
[[ -f "$STATE_ROOT/device-identity.json" ]] || die "Centinal26 device identity is missing."
mkdir -p "$BIN" "$ROOT/state" "$ROOT/logs"
chmod 700 "$BIN" "$ROOT/state" "$ROOT/logs" 2>/dev/null || true

cat > "$PROVIDER" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

json_escape(){
  local s="$1"
  s=${s//\\/\\\\}; s=${s//\"/\\\"}; s=${s//$'\n'/\\n}; s=${s//$'\r'/\\r}; s=${s//$'\t'/\\t}
  printf '%s' "$s"
}

present(){ command -v "$1" >/dev/null 2>&1; }

catalog(){
  local first=1 cap cmd ok
  printf '{"schema":"centinal26-capability-provider/v1","capabilities":['
  while IFS='|' read -r cap cmd; do
    [[ -n "$cap" ]] || continue
    if present "$cmd"; then ok=true; else ok=false; fi
    [[ "$first" -eq 1 ]] || printf ','
    first=0
    printf '{"capability":"%s","present":%s}' "$(json_escape "$cap")" "$ok"
  done <<'EOF'
python.runtime|python
git.client|git
node.runtime|node
json.jq|jq
hash.sha256|sha256sum
process.procps|pgrep
crypto.openssl|openssl
network.curl|curl
termux.api.cli|termux-wake-lock
EOF
  printf ']}\n'
}

if [[ "${1:-}" == "--catalog" ]]; then catalog; exit 0; fi
cap="${1:-}"
[[ "$cap" =~ ^[a-z0-9._-]{1,64}$ ]] || { echo '{"status":"rejected","reason":"invalid_capability_name"}' >&2; exit 64; }

package=""; verify1=""; verify2=""; fallback=""
case "$cap" in
  python.runtime) package="python"; verify1="python" ;;
  git.client) package="git"; verify1="git" ;;
  node.runtime) package="nodejs-lts"; fallback="nodejs"; verify1="node"; verify2="npm" ;;
  json.jq) package="jq"; verify1="jq" ;;
  hash.sha256) package="coreutils"; verify1="sha256sum" ;;
  process.procps) package="procps"; verify1="pgrep" ;;
  crypto.openssl) package="openssl"; verify1="openssl" ;;
  network.curl) package="curl"; verify1="curl" ;;
  termux.api.cli) package="termux-api"; verify1="termux-wake-lock" ;;
  *) printf '{"capability":"%s","status":"rejected","reason":"not_in_registry"}\n' "$(json_escape "$cap")" >&2; exit 65 ;;
esac

if present "$verify1" && { [[ -z "$verify2" ]] || present "$verify2"; }; then
  printf '{"capability":"%s","package":"%s","status":"present"}\n' "$(json_escape "$cap")" "$(json_escape "$package")"
  exit 0
fi

if ! pkg install -y "$package"; then
  [[ -n "$fallback" ]] || { printf '{"capability":"%s","package":"%s","status":"failed"}\n' "$(json_escape "$cap")" "$(json_escape "$package")" >&2; exit 70; }
  pkg install -y "$fallback" || { printf '{"capability":"%s","package":"%s","fallback":"%s","status":"failed"}\n' "$(json_escape "$cap")" "$(json_escape "$package")" "$(json_escape "$fallback")" >&2; exit 70; }
fi

present "$verify1" || { printf '{"capability":"%s","status":"failed","reason":"verification_missing_%s"}\n' "$(json_escape "$cap")" "$(json_escape "$verify1")" >&2; exit 71; }
[[ -z "$verify2" ]] || present "$verify2" || { printf '{"capability":"%s","status":"failed","reason":"verification_missing_%s"}\n' "$(json_escape "$cap")" "$(json_escape "$verify2")" >&2; exit 71; }
printf '{"capability":"%s","package":"%s","status":"installed"}\n' "$(json_escape "$cap")" "$(json_escape "${fallback:-$package}")"
SH
chmod 700 "$PROVIDER"

cat > "$WORKER" <<'NODE'
import { createClient } from "@base44/sdk";
import { readFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import os from "node:os";
import path from "node:path";

const VERSION = "centinal26-base44-fleet-worker/1.1.0";
const PROTOCOL = "frost-call/1.0";
const ROOT = process.env.AUTOMATION_BRIDGE_ROOT || path.join(os.homedir(), ".automation_bridge");
const STATE_ROOT = process.env.CENTINAL26_HOME || path.join(os.homedir(), ".local/state/centinal26");
const APP_ID = process.env.BASE44_APP_ID || "6a484dc22829dd2fd4a7bcd1";
const EMAIL = process.env.BASE44_WORKER_EMAIL || process.env.BASE44_EMAIL || "";
const TOKEN = process.env.BASE44_TOKEN || "";
const PASSWORD = process.env.BASE44_PASSWORD || "";
const POLL_MS = Math.max(5000, Number(process.env.POLL_SECONDS || 8) * 1000);
const HEARTBEAT_MS = 60_000;
const MAX_CAPTURE = 65536;
const ALLOWED = new Set(["system.health", "system.capabilities", "capability.ensure"]);
const PROVIDER = path.join(ROOT, "bin", "capability-ensure");
const identity = JSON.parse(await readFile(path.join(STATE_ROOT, "device-identity.json"), "utf8"));
const instanceId = String(identity.device_id || "");
const bootId = (await readFile("/proc/sys/kernel/random/boot_id", "utf8").catch(()=>"unknown\n")).trim();
const startedAt = new Date().toISOString();

function now(){ return new Date().toISOString(); }
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
function allowed(op){ return ALLOWED.has(String(op || "")); }
function requestedCapability(job){
  for (const raw of [job.payload_json, job.parameters_json]) {
    if (!raw) continue;
    try {
      const parsed = JSON.parse(raw);
      const c = parsed?.capability;
      if (typeof c === "string" && /^[a-z0-9._-]{1,64}$/.test(c)) return c;
    } catch {}
  }
  return "";
}
function providerEnv(){
  const out = {};
  for (const key of ["PATH","HOME","PREFIX","TMPDIR","LANG","LD_LIBRARY_PATH"]) if (process.env[key]) out[key] = process.env[key];
  return out;
}
function runProvider(args){
  return new Promise((resolve) => {
    const child = spawn(PROVIDER, args, {shell:false, env:providerEnv(), stdio:["ignore","pipe","pipe"]});
    let stdout="", stderr="";
    const add=(kind,chunk)=>{ const s=String(chunk); if(kind==="out") stdout=(stdout+s).slice(-MAX_CAPTURE); else stderr=(stderr+s).slice(-MAX_CAPTURE); };
    child.stdout.on("data", c=>add("out",c));
    child.stderr.on("data", c=>add("err",c));
    child.on("error", e=>resolve({exit_code:127,stdout,stderr:String(e?.message||e)}));
    child.on("close", code=>resolve({exit_code:Number(code ?? 1),stdout:stdout.trim(),stderr:stderr.trim()}));
  });
}
if (process.argv.includes("--self-test")) {
  const checks = [
    ["allow-health", allowed("system.health")],
    ["allow-capabilities", allowed("system.capabilities")],
    ["allow-bounded-install", allowed("capability.ensure")],
    ["deny-shell", !allowed("shell.exec")],
    ["deny-workflow", !allowed("workflow.execute")],
    ["provider-path-fixed", PROVIDER.endsWith("/.automation_bridge/bin/capability-ensure") || PROVIDER.endsWith("/bin/capability-ensure")],
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
    worker_email:EMAIL, instance_id:instanceId, status, last_seen:now(), version:VERSION,
    capabilities_json:JSON.stringify({role:"capability-routed-fleet-executor", arbitrary_shell:false, capability_provider:"bounded-registry-v1", boot_id:bootId, process_started_at:startedAt, ...extra}),
    protocol_versions_json:JSON.stringify([PROTOCOL]), supported_operations_json:JSON.stringify([...ALLOWED]),
    platform:"android/termux", runtime:`node/${process.version}`, boot_id:bootId, max_concurrency:1,
    promotion_stage:"HOST_VALIDATED", supervisor_status:"running"
  };
  if (!workerRowId) {
    const rows = await b.entities.AutomationWorker.filter({worker_email:EMAIL, instance_id:instanceId}, "-updated_date", 1, 0).catch(()=>[]);
    workerRowId = rows?.[0]?.id || "";
  }
  if (workerRowId) await b.entities.AutomationWorker.update(workerRowId, data);
  else { const row=await b.entities.AutomationWorker.create(data); workerRowId=row?.id||""; }
}
async function execute(job){
  const op=String(job.operation||"");
  if(!allowed(op)) return false;
  const claimed=now();
  await b.entities.AutomationJob.update(job.id,{status:"claimed",worker_instance_id:instanceId,claimed_at:claimed,heartbeat_at:claimed,lease_until:new Date(Date.now()+300000).toISOString(),attempt:Number(job.attempt||0)+1});
  await b.entities.AutomationJob.update(job.id,{status:"running",started_at:now(),heartbeat_at:now()});
  let result;
  if(op==="system.health") {
    result={status:"healthy",platform:"android/termux",worker_instance_id:instanceId,boot_id:bootId,component:VERSION,protocol:PROTOCOL,arbitrary_shell:false,probe_executed_at:now()};
  } else if(op==="system.capabilities") {
    const provider=await runProvider(["--catalog"]);
    result={platform:"android/termux",worker_instance_id:instanceId,boot_id:bootId,protocol_versions:[PROTOCOL],operations:[...ALLOWED],arbitrary_shell:false,capability_routing:true,provider};
  } else {
    const capability=requestedCapability(job);
    if(!capability){
      const done=now();
      await b.entities.AutomationJob.update(job.id,{status:"failed",finished_at:done,heartbeat_at:done,lease_until:done,error_message:"capability.ensure requires parameters_json or payload_json containing a registry capability",result_summary:JSON.stringify({status:"rejected",reason:"missing_capability"})});
      return true;
    }
    const provider=await runProvider([capability]);
    result={operation:op,capability,provider,worker_instance_id:instanceId,boot_id:bootId};
    if(provider.exit_code!==0){
      const done=now();
      await b.entities.AutomationJob.update(job.id,{status:"failed",finished_at:done,heartbeat_at:done,lease_until:done,error_message:`capability provider exit ${provider.exit_code}`,result_summary:JSON.stringify(result)});
      await upsertWorker("online",{last_operation:op,last_job_id:job.id,last_capability_result:result});
      return true;
    }
  }
  const done=now();
  await b.entities.AutomationJob.update(job.id,{status:"completed",finished_at:done,heartbeat_at:done,lease_until:done,result_summary:JSON.stringify(result),error_message:""});
  await upsertWorker("online",{last_operation:op,last_job_id:job.id});
  return true;
}
console.log(`[${VERSION}] email=${EMAIL} instance=${instanceId} boot_id=${bootId}`);
await upsertWorker("online",{startup:true});
let lastHeartbeat=Date.now();
while(true){
  try{
    const jobs=await b.entities.AutomationJob.filter({status:"queued",worker_email:EMAIL,job_type:"frost_call"},"-priority",20,0);
    for(const job of jobs||[]){ const op=String(job.operation||""); if(!allowed(op)) continue; try{await execute(job);}catch(e){console.error(`[job-fail] ${job.id}`,e?.stack||e);} }
    if(Date.now()-lastHeartbeat>=HEARTBEAT_MS){await upsertWorker("online");lastHeartbeat=Date.now();}
  }catch(e){console.error(`[cycle-error ${now()}]`,e?.stack||e);}
  await sleep(POLL_MS);
}
NODE
chmod 600 "$WORKER"

set -a
# shellcheck disable=SC1090
source "$CFG"
set +a
node --check "$WORKER"
node "$WORKER" --self-test
"$PROVIDER" --catalog >/dev/null

if [[ -f "$PIDFILE" ]]; then
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  rm -f "$PIDFILE"
fi
nohup node "$WORKER" >> "$LOG" 2>&1 </dev/null &
echo $! > "$PIDFILE"
chmod 600 "$PIDFILE"
sleep 1
kill -0 "$(cat "$PIDFILE")" 2>/dev/null || die "Upgraded fleet worker failed to start."

say "Bounded capability provider installed and fleet worker upgraded to 1.1.0."
say "Allowed remote operations: system.health, system.capabilities, capability.ensure."
say "capability.ensure accepts only the hardcoded registry; arbitrary shell/package names remain denied."
