#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

VERSION="2.0.0"
REPO="${CENTINAL26_ROOT:-$HOME/centinal26}"
STATE="${FROST_PERSISTENT_STATE:-$HOME/.frost_persistent}"
BIN="${HOME}/.local/bin"
INTERVAL="${FROST_PERSISTENT_INTERVAL:-3600}"
SELF_TEST=0
NO_DAEMON="${FROST_NO_DAEMON:-0}"

for arg in "$@"; do
  case "$arg" in
    --self-test) SELF_TEST=1 ;;
    --no-daemon) NO_DAEMON=1 ;;
    --version) printf '%s\n' "$VERSION"; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

mkdir -p "$STATE" "$BIN" "$HOME/.termux/boot"
LOG="$STATE/install.log"
exec > >(tee -a "$LOG") 2>&1

say() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }

atomic_write() {
  local target="$1" tmp
  tmp="${target}.tmp.$$"
  cat > "$tmp"
  chmod 600 "$tmp" 2>/dev/null || true
  mv -f "$tmp" "$target"
}

self_test() {
  local t
  t="$(mktemp -d)"
  trap 'rm -rf "$t"' RETURN
  printf 'alpha\n' | atomic_write "$t/a"
  [[ "$(cat "$t/a")" == alpha ]] || fail 'atomic_write failed'
  mkdir "$t/lock"
  if mkdir "$t/lock" 2>/dev/null; then fail 'lock exclusivity failed'; fi
  python - "$t/state.json" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1])
obj={"schema":2,"goal_reached":False,"checks":{"repo_sync":True}}
p.write_text(json.dumps(obj,sort_keys=True)+"\n")
assert json.loads(p.read_text())["schema"] == 2
PY
  say 'SELF_TEST PASS'
}

if [[ "$SELF_TEST" == 1 ]]; then
  self_test
  exit 0
fi

command -v git >/dev/null 2>&1 || fail 'git is required'
command -v python >/dev/null 2>&1 || fail 'python is required'

BASE_INSTALLER="$REPO/install/2026-08-22__INSTALL_ALL_CYBERSECURITY_AUTOMATION_SKYNET_TERMUX_v1.0.sh"
if [[ -f "$BASE_INSTALLER" ]]; then
  say 'Reconciling base installation'
  FROST_NO_DAEMON=1 SKYNET_NO_DAEMON=1 bash "$BASE_INSTALLER"
else
  say 'Base installer not present; installing persistence layer only'
fi

SUPERVISOR="$BIN/frost-persistent-supervisor"
cat > "$SUPERVISOR" <<'SUPERVISOR_EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077
REPO="${CENTINAL26_ROOT:-$HOME/centinal26}"
STATE="${FROST_PERSISTENT_STATE:-$HOME/.frost_persistent}"
INTERVAL="${FROST_PERSISTENT_INTERVAL:-3600}"
MODE="${1:---once}"
mkdir -p "$STATE"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$STATE/supervisor.log"; }

acquire_lock() {
  if mkdir "$STATE/lock" 2>/dev/null; then
    trap 'rmdir "$STATE/lock" 2>/dev/null || true' EXIT INT TERM
    return 0
  fi
  return 1
}

json_state() {
  python - "$STATE/project_state.json" "$@" <<'PY'
import hashlib, json, os, pathlib, sys, time
out=pathlib.Path(sys.argv[1])
vals=sys.argv[2:]
keys=["repo_sync","repo_clean","pair_ok","skynet_ok","device_report_ok","head","origin","detail"]
d=dict(zip(keys,vals))
checks={k:(d[k]=="1") for k in ["repo_sync","repo_clean","pair_ok","skynet_ok","device_report_ok"]}
goal=all(checks.values())
obj={
 "schema":2,
 "updated_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
 "checks":checks,
 "goal_reached":goal,
 "head":d.get("head",""),
 "origin_main":d.get("origin",""),
 "detail":d.get("detail",""),
}
payload=json.dumps(obj,indent=2,sort_keys=True)+"\n"
tmp=out.with_suffix(out.suffix+".tmp")
tmp.write_text(payload)
os.replace(tmp,out)
pathlib.Path(str(out)+".sha256").write_text(hashlib.sha256(out.read_bytes()).hexdigest()+"  "+out.name+"\n")
if goal:
    marker=out.parent/"PROJECT_GOAL_REACHED"
    marker.write_text(obj["updated_at_utc"]+"\n")
PY
}

run_once() {
  acquire_lock || { log 'another supervisor instance is active'; return 0; }
  local repo_sync=0 repo_clean=0 pair_ok=0 skynet_ok=0 device_ok=0 head='' origin='' detail=''

  if [[ -d "$REPO/.git" ]]; then
    git -C "$REPO" fetch --prune origin main >>"$STATE/supervisor.log" 2>&1 || detail="git_fetch_failed"
    head="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || true)"
    origin="$(git -C "$REPO" rev-parse origin/main 2>/dev/null || true)"
    [[ -z "$(git -C "$REPO" status --porcelain 2>/dev/null)" ]] && repo_clean=1
    if [[ -n "$head" && -n "$origin" ]]; then
      if [[ "$head" == "$origin" ]]; then
        repo_sync=1
      else
        base="$(git -C "$REPO" merge-base "$head" "$origin" 2>/dev/null || true)"
        if [[ "$base" == "$head" && "$repo_clean" == 1 ]]; then
          git -C "$REPO" merge --ff-only origin/main >>"$STATE/supervisor.log" 2>&1 || true
          head="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || true)"
          [[ "$head" == "$origin" ]] && repo_sync=1
        fi
      fi
    fi
  else
    detail="repo_missing"
  fi

  if command -v frost-pair-update >/dev/null 2>&1; then
    frost-pair-update --status-only >>"$STATE/supervisor.log" 2>&1 && pair_ok=1 || true
  elif [[ -x "${PREFIX:-}/bin/frost-pair-update" ]]; then
    "${PREFIX}/bin/frost-pair-update" --status-only >>"$STATE/supervisor.log" 2>&1 && pair_ok=1 || true
  fi

  if [[ -x "$HOME/.local/bin/skynet" ]]; then
    "$HOME/.local/bin/skynet" verify-audit >>"$STATE/supervisor.log" 2>&1 && skynet_ok=1 || true
  fi

  for p in "$REPO/artifacts/DEVICE_VALIDATION_REPORT.json" "$REPO/device_validation/DEVICE_VALIDATION_REPORT.json" "$STATE/DEVICE_VALIDATION_REPORT.json"; do
    if [[ -s "$p" ]]; then
      python - "$p" <<'PY' >/dev/null 2>&1 && device_ok=1 || true
import json,sys
x=json.load(open(sys.argv[1]))
status=str(x.get("status",x.get("result",""))).upper()
origin=str(x.get("origin",x.get("execution_origin",""))).upper()
assert status in {"PASS","VERIFIED","SUCCESS"}
assert "TERMUX" in origin or "ANDROID" in origin or bool(x.get("device_origin_verified"))
PY
      [[ "$device_ok" == 1 ]] && break
    fi
  done

  json_state "$repo_sync" "$repo_clean" "$pair_ok" "$skynet_ok" "$device_ok" "$head" "$origin" "$detail"
  log "cycle repo_sync=$repo_sync repo_clean=$repo_clean pair_ok=$pair_ok skynet_ok=$skynet_ok device_ok=$device_ok"
}

case "$MODE" in
  --once) run_once ;;
  --loop)
    while :; do
      run_once || true
      sleep "$INTERVAL"
    done
    ;;
  --status)
    [[ -f "$STATE/project_state.json" ]] && cat "$STATE/project_state.json" || printf '{"goal_reached":false,"detail":"no_state_yet"}\n'
    ;;
  *) printf 'usage: %s [--once|--loop|--status]\n' "$0" >&2; exit 2 ;;
esac
SUPERVISOR_EOF
chmod 700 "$SUPERVISOR"

BOOT="$HOME/.termux/boot/frost-persistent-autopilot.sh"
cat > "$BOOT" <<'BOOT_EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -u
export PATH="$HOME/.local/bin:${PREFIX:-/data/data/com.termux/files/usr}/bin:$PATH"
STATE="${FROST_PERSISTENT_STATE:-$HOME/.frost_persistent}"
mkdir -p "$STATE"
if ! pgrep -f "$HOME/.local/bin/frost-persistent-supervisor --loop" >/dev/null 2>&1; then
  nohup "$HOME/.local/bin/frost-persistent-supervisor" --loop >>"$STATE/boot.log" 2>&1 &
fi
BOOT_EOF
chmod 700 "$BOOT"

STATUS="$BIN/frost-project-goal"
cat > "$STATUS" <<'STATUS_EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
STATE="${FROST_PERSISTENT_STATE:-$HOME/.frost_persistent}"
"$HOME/.local/bin/frost-persistent-supervisor" --once
cat "$STATE/project_state.json"
STATUS_EOF
chmod 700 "$STATUS"

if [[ -n "${PREFIX:-}" && -d "$PREFIX/bin" && -w "$PREFIX/bin" ]]; then
  ln -sfn "$SUPERVISOR" "$PREFIX/bin/frost-persistent-supervisor"
  ln -sfn "$STATUS" "$PREFIX/bin/frost-project-goal"
fi

say 'Running installation verification'
"$SUPERVISOR" --once
python - "$STATE/project_state.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x["schema"] == 2
assert set(x["checks"]) == {"repo_sync","repo_clean","pair_ok","skynet_ok","device_report_ok"}
print("state_schema=PASS")
print("goal_reached="+str(x["goal_reached"]).lower())
PY

if [[ "$NO_DAEMON" != 1 ]]; then
  if ! pgrep -f "$SUPERVISOR --loop" >/dev/null 2>&1; then
    nohup "$SUPERVISOR" --loop >>"$STATE/daemon.log" 2>&1 &
  fi
fi

say "Persistent autopilot v$VERSION installed"
say "status command: frost-project-goal"
say "state: $STATE/project_state.json"
say 'A project-goal marker is emitted only after every verification gate passes.'
