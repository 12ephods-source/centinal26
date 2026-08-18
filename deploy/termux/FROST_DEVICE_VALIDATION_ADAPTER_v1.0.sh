#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

ROOT="${AUTOMATION_BRIDGE_ROOT:-$HOME/.automation_bridge}"
STATE_ROOT="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
CFG="$ROOT/bridge.env"
WORKER="$ROOT/fleet_worker.mjs"
BIN="$ROOT/bin"
ADAPTER="$BIN/device-validation-capability"
PIDFILE="$ROOT/state/fleet_worker.pid"
LOG="$ROOT/logs/fleet_worker.log"

say(){ printf '[frost-device-validation] %s\n' "$*"; }
die(){ printf '[frost-device-validation] ERROR: %s\n' "$*" >&2; exit 1; }

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) die "Run this inside Termux on Android." ;;
esac

for c in git python node sha256sum; do
  command -v "$c" >/dev/null 2>&1 || die "Required command unavailable: $c"
done
[[ -f "$CFG" ]] || die "Base44 worker config missing: $CFG"
[[ -f "$WORKER" ]] || die "Base44 fleet worker missing: $WORKER"
[[ -f "$STATE_ROOT/device-identity.json" ]] || die "Centinal26 device identity missing."
mkdir -p "$BIN" "$ROOT/state" "$ROOT/logs"
chmod 700 "$BIN" "$ROOT/state" "$ROOT/logs" 2>/dev/null || true

cat > "$ADAPTER" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

REPO="https://github.com/12ephods-source/centinal26.git"
PERSIST_SHA="20dcbb6dae29eee302e2d566c2a4270d1b657971"
STATE_ROOT="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
SOURCE_ROOT="${CENTINAL26_FLEET_ROOT:-$HOME/.local/share/centinal26-fleet-bootstrap}/persistence-$PERSIST_SHA"
MODE="${1:-status}"

die_json(){
  python - "$1" <<'PY'
import json,sys
print(json.dumps({"status":"rejected","reason":sys.argv[1]}, sort_keys=True, separators=(",",":")))
PY
  exit 64
}

case "$MODE" in
  status|ensure|verify) ;;
  *) die_json "unsupported_device_validation_operation" ;;
esac

fetch_source(){
  if [[ -d "$SOURCE_ROOT/.git" ]] &&
     [[ "$(git -C "$SOURCE_ROOT" rev-parse HEAD 2>/dev/null || true)" == "$PERSIST_SHA" ]] &&
     [[ -z "$(git -C "$SOURCE_ROOT" status --porcelain --untracked-files=all 2>/dev/null || true)" ]]; then
    return 0
  fi
  [[ ! -e "$SOURCE_ROOT" ]] || die_json "pinned_source_present_but_not_exact_clean_checkout"
  mkdir -p "$SOURCE_ROOT"
  git -C "$SOURCE_ROOT" init -q
  git -C "$SOURCE_ROOT" remote add origin "$REPO"
  git -C "$SOURCE_ROOT" fetch -q --depth 1 origin "$PERSIST_SHA"
  git -C "$SOURCE_ROOT" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$SOURCE_ROOT" rev-parse HEAD)" == "$PERSIST_SHA" ]] || die_json "pinned_source_commit_mismatch"
  [[ -z "$(git -C "$SOURCE_ROOT" status --porcelain --untracked-files=all)" ]] || die_json "pinned_source_dirty"
}

fetch_source
export CENTINAL26_HOME="$STATE_ROOT"
export PYTHONPATH="$SOURCE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

identity="$(python -S -m centinal26.device_campaign_cli identity)"
device_id="$(printf '%s' "$identity" | python -c 'import json,sys; print(json.load(sys.stdin)["device_id"])')"
campaign="$STATE_ROOT/device-validation/devices/$device_id/current"
checkpoint="$campaign/device-campaign-checkpoint.json"
boot_id="$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || printf unknown)"

status_json(){
  local phase="$1"
  DEVICE_ID="$device_id" CAMPAIGN="$campaign" CHECKPOINT="$checkpoint" BOOT_ID="$boot_id" PHASE="$phase" PERSIST_SHA="$PERSIST_SHA" python - <<'PY'
import json,os
print(json.dumps({
  "schema":"centinal26-device-validation-capability/v1",
  "status":os.environ["PHASE"],
  "device_id":os.environ["DEVICE_ID"],
  "boot_id":os.environ["BOOT_ID"].strip(),
  "campaign":os.environ["CAMPAIGN"],
  "checkpoint_exists":os.path.isfile(os.environ["CHECKPOINT"]),
  "source_commit":os.environ["PERSIST_SHA"],
  "reboot_performed_by_adapter":False,
}, sort_keys=True, separators=(",",":")))
PY
}

if [[ "$MODE" == "status" ]]; then
  if [[ -f "$checkpoint" ]]; then status_json "PRE_REBOOT_EVIDENCE_PRESENT"; else status_json "CAMPAIGN_NOT_STARTED"; fi
  exit 0
fi

if [[ "$MODE" == "ensure" ]]; then
  if [[ ! -f "$checkpoint" ]]; then
    bash "$SOURCE_ROOT/scripts/device-validation-termux.sh"
  fi
  [[ -f "$checkpoint" ]] || die_json "campaign_checkpoint_not_created"
  status_json "WAITING_FOR_PHYSICAL_REBOOT_OR_POST_REBOOT_VERIFY"
  exit 0
fi

[[ -f "$checkpoint" ]] || die_json "campaign_checkpoint_missing_run_device_validation_ensure_first"
python -S -m centinal26.device_campaign_cli verify --campaign "$campaign"
SH
chmod 700 "$ADAPTER"

python - "$WORKER" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

checks = [
    'const VERSION = "centinal26-base44-fleet-worker/1.1.0";',
    'const ALLOWED = new Set(["system.health", "system.capabilities", "capability.ensure"]);',
    'const PROVIDER = path.join(ROOT, "bin", "capability-ensure");',
    '["allow-bounded-install", allowed("capability.ensure")]',
]
for marker in checks:
    if marker not in s:
        raise SystemExit(f"worker source is not the expected v1.1 contract; missing marker: {marker}")

s = s.replace(
    'const VERSION = "centinal26-base44-fleet-worker/1.1.0";',
    'const VERSION = "centinal26-base44-fleet-worker/1.2.0";',
    1,
)
s = s.replace(
    'const ALLOWED = new Set(["system.health", "system.capabilities", "capability.ensure"]);',
    'const ALLOWED = new Set(["system.health", "system.capabilities", "capability.ensure", "device.validation.status", "device.validation.ensure", "device.validation.verify"]);',
    1,
)
s = s.replace(
    'const PROVIDER = path.join(ROOT, "bin", "capability-ensure");',
    'const PROVIDER = path.join(ROOT, "bin", "capability-ensure");\nconst DEVICE_VALIDATION = path.join(ROOT, "bin", "device-validation-capability");',
    1,
)

needle = '''function runProvider(args){
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
'''
addition = needle + '''function runDeviceValidation(mode){
  return new Promise((resolve) => {
    const child = spawn(DEVICE_VALIDATION, [mode], {shell:false, env:providerEnv(), stdio:["ignore","pipe","pipe"]});
    let stdout="", stderr="";
    const add=(kind,chunk)=>{ const s=String(chunk); if(kind==="out") stdout=(stdout+s).slice(-MAX_CAPTURE); else stderr=(stderr+s).slice(-MAX_CAPTURE); };
    child.stdout.on("data", c=>add("out",c));
    child.stderr.on("data", c=>add("err",c));
    child.on("error", e=>resolve({exit_code:127,stdout,stderr:String(e?.message||e)}));
    child.on("close", code=>resolve({exit_code:Number(code ?? 1),stdout:stdout.trim(),stderr:stderr.trim()}));
  });
}
'''
if needle not in s:
    raise SystemExit("expected fixed provider runner block missing")
s = s.replace(needle, addition, 1)

s = s.replace(
    '    ["allow-bounded-install", allowed("capability.ensure")],',
    '    ["allow-bounded-install", allowed("capability.ensure")],\n'
    '    ["allow-device-validation-status", allowed("device.validation.status")],\n'
    '    ["allow-device-validation-ensure", allowed("device.validation.ensure")],\n'
    '    ["allow-device-validation-verify", allowed("device.validation.verify")],\n'
    '    ["deny-remote-reboot", !allowed("device.reboot")],',
    1,
)

old = '''  } else {
    const capability=requestedCapability(job);
'''
new = '''  } else if(op==="device.validation.status" || op==="device.validation.ensure" || op==="device.validation.verify") {
    const mode = op.endsWith(".status") ? "status" : (op.endsWith(".ensure") ? "ensure" : "verify");
    const validation = await runDeviceValidation(mode);
    result={operation:op,device_validation:validation,worker_instance_id:instanceId,boot_id:bootId,physical_reboot_performed:false};
    if(validation.exit_code!==0){
      const done=now();
      await b.entities.AutomationJob.update(job.id,{status:"failed",finished_at:done,heartbeat_at:done,lease_until:done,error_message:`device validation adapter exit ${validation.exit_code}`,result_summary:JSON.stringify(result)});
      await upsertWorker("online",{last_operation:op,last_job_id:job.id,last_device_validation_result:result});
      return true;
    }
  } else {
    const capability=requestedCapability(job);
'''
if old not in s:
    raise SystemExit("expected execute dispatch block missing")
s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
PY

node --check "$WORKER"
node "$WORKER" --self-test
"$ADAPTER" status >/dev/null

if [[ -f "$PIDFILE" ]]; then
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  rm -f "$PIDFILE"
fi
set -a
# shellcheck disable=SC1090
source "$CFG"
set +a
nohup node "$WORKER" >> "$LOG" 2>&1 </dev/null &
echo $! > "$PIDFILE"
chmod 600 "$PIDFILE"
sleep 1
kill -0 "$(cat "$PIDFILE")" 2>/dev/null || die "Upgraded fleet worker failed to start."

say "Installed registered Android device-validation capability."
say "Allowed added operations: device.validation.status, device.validation.ensure, device.validation.verify."
say "Remote reboot remains disabled; the physical reboot must still be performed by the device user."
say "No arbitrary command, path, package, repository, or source commit can be supplied by a remote job."
