#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

VERSION="3.1"
APP="Frost Android Evidence Guardian"
BASE="${FROST_EVIDENCE_HOME:-$HOME/.frost_sentinel/physical_evidence}"
RUNS="$BASE/runs"
LEDGER="$BASE/custody_chain.tsv"
STATE="$BASE/state"
LOCK="$BASE/.collect.lock"
BOOT="$HOME/.termux/boot/frost-physical-evidence-guardian.sh"
INTERVAL="${FROST_INTERVAL_SECONDS:-21600}"   # 6 hours
CASE_ID="${CASE_ID:-RF-CYBER-2026-001}"
OPERATOR="${OPERATOR:-RF}"
EXPORT_DIR="${FROST_EXPORT_DIR:-$HOME/storage/shared/FrostSentinelEvidence}"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
die(){ printf 'ERROR: %s\n' "$*" >&2; exit 1; }
have(){ command -v "$1" >/dev/null 2>&1; }
sha(){ sha256sum "$1" | awk '{print $1}'; }

runtime_class() {
  if [[ -d /data/data/com.termux/files/usr ]] && [[ "${PREFIX:-}" == *"com.termux"* ]]; then
    printf 'ANDROID_TERMUX'
  elif [[ "${FROST_ANDROID_FIXTURE:-0}" == "1" ]]; then
    printf 'ANDROID_FIXTURE'
  else
    printf 'HOST_OR_SESSION'
  fi
}

claim_scope() {
  case "$(runtime_class)" in
    ANDROID_TERMUX) printf 'DEVICE_ORIGIN_AND_SOFTWARE' ;;
    ANDROID_FIXTURE) printf 'ANDROID_LOGIC_AND_SOFTWARE' ;;
    *) printf 'SOFTWARE_ONLY' ;;
  esac
}

init_dirs() {
  mkdir -p "$RUNS" "$STATE"
  chmod 700 "$BASE" "$RUNS" "$STATE" || true
  touch "$LEDGER"
  chmod 600 "$LEDGER" || true
}

device_id() {
  local v=""
  if have getprop; then
    v="$(getprop ro.serialno 2>/dev/null || true)"
    [[ -n "$v" && "$v" != "unknown" ]] || v="$(getprop ro.boot.serialno 2>/dev/null || true)"
  fi
  [[ -n "$v" ]] || v="$(uname -n 2>/dev/null || printf unknown)"
  printf '%s' "$v"
}

safe_cmd() {
  local outfile="$1"; shift
  {
    printf '# captured_utc=%s\n' "$(ts)"
    printf '# command='
    printf '%q ' "$@"
    printf '\n'
    "$@"
  } >"$outfile" 2>&1 || {
    local rc=$?
    printf '\n# exit_code=%s\n' "$rc" >>"$outfile"
    return 0
  }
}

verify_run() {
  local d="$1"
  [[ -d "$d" ]] || return 1
  [[ -f "$d/SHA256SUMS.txt" ]] || return 1
  (cd "$d" && sha256sum -c SHA256SUMS.txt >/dev/null)
}

verify_all() {
  init_dirs
  local bad=0 total=0
  while IFS= read -r -d '' d; do
    total=$((total+1))
    if verify_run "$d"; then
      printf 'PASS %s\n' "$(basename "$d")"
    else
      printf 'FAIL %s\n' "$(basename "$d")"
      bad=$((bad+1))
    fi
  done < <(find "$RUNS" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
  printf 'verified_runs=%d failures=%d\n' "$total" "$bad"
  [[ "$bad" -eq 0 ]]
}

ledger_prev_hash() {
  if [[ -s "$LEDGER" ]]; then
    tail -n 1 "$LEDGER" | awk -F'\t' '{print $1}'
  else
    printf '%064d' 0
  fi
}

append_ledger() {
  local run_id="$1" manifest_hash="$2" archive_hash="$3"
  local prev record record_hash
  prev="$(ledger_prev_hash)"
  record="$(printf '%s\t%s\t%s\t%s\t%s\t%s\t%s' \
    "$(ts)" "$CASE_ID" "$OPERATOR" "$run_id" "$manifest_hash" "$archive_hash" "$prev")"
  record_hash="$(printf '%s' "$record" | sha256sum | awk '{print $1}')"
  printf '%s\t%s\n' "$record_hash" "$record" >> "$LEDGER"
  sync "$LEDGER" 2>/dev/null || true
}

protect_run() {
  local d="$1"
  find "$d" -type f -exec chmod 400 {} + 2>/dev/null || true
  find "$d" -type d -exec chmod 500 {} + 2>/dev/null || true
}

collect() {
  init_dirs

  if ! mkdir "$LOCK" 2>/dev/null; then
    die "collection already running or stale lock exists: $LOCK"
  fi
  trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT INT TERM

  if ! verify_all >"$STATE/preflight_verify.txt" 2>&1; then
    cp "$STATE/preflight_verify.txt" "$STATE/TAMPER_ALERT_$(date -u +%Y%m%dT%H%M%SZ).txt"
    die "prior sealed evidence failed verification; preserved tamper alert and stopped"
  fi

  local stamp run_id d
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  run_id="${CASE_ID}_${stamp}_$RANDOM"
  d="$RUNS/$run_id"
  mkdir -p "$d"/{device,android,network,process,termux,integrity,meta}
  chmod 700 "$d"

  printf '%s\n' "$run_id" >"$d/meta/execution_id.txt"
  printf '%s\n' "$(ts)" >"$d/meta/acquisition_started_utc.txt"
  printf '%s\n' "$CASE_ID" >"$d/meta/case_id.txt"
  printf '%s\n' "$OPERATOR" >"$d/meta/operator.txt"
  printf '%s\n' "$VERSION" >"$d/meta/collector_version.txt"
  printf '%s\n' "$(runtime_class)" >"$d/meta/runtime_class.txt"
  printf '%s\n' "$(claim_scope)" >"$d/meta/claim_scope.txt"
  printf '%s\n' "$(device_id)" >"$d/meta/device_identity_observed.txt"
  printf 'source=android_property_or_hostname_fallback\n' >"$d/meta/device_identity_source.txt"

  safe_cmd "$d/device/uname.txt" uname -a
  safe_cmd "$d/device/id.txt" id
  safe_cmd "$d/device/date.txt" date
  have getprop && safe_cmd "$d/device/getprop.txt" getprop
  have termux-info && safe_cmd "$d/termux/termux-info.txt" termux-info
  have termux-battery-status && safe_cmd "$d/termux/battery.json" termux-battery-status

  have settings && {
    safe_cmd "$d/android/settings_global.txt" settings list global
    safe_cmd "$d/android/settings_secure.txt" settings list secure
    safe_cmd "$d/android/settings_system.txt" settings list system
  }

  have pm && {
    safe_cmd "$d/android/packages_all.txt" pm list packages -f -U -i
    safe_cmd "$d/android/packages_disabled.txt" pm list packages -d
  }

  have dumpsys && {
    safe_cmd "$d/android/device_policy.txt" dumpsys device_policy
    safe_cmd "$d/android/accessibility.txt" dumpsys accessibility
    safe_cmd "$d/android/notification.txt" dumpsys notification
    safe_cmd "$d/android/connectivity.txt" dumpsys connectivity
    safe_cmd "$d/android/package_service.txt" dumpsys package
    safe_cmd "$d/android/battery_history.txt" dumpsys batterystats
    safe_cmd "$d/android/usage_stats.txt" dumpsys usagestats
    safe_cmd "$d/android/activity_services.txt" dumpsys activity services
  }

  have ip && {
    safe_cmd "$d/network/ip_addr.txt" ip addr
    safe_cmd "$d/network/ip_route.txt" ip route
    safe_cmd "$d/network/ip_rule.txt" ip rule
  }
  have ss && safe_cmd "$d/network/sockets.txt" ss -tunap
  have ps && safe_cmd "$d/process/processes.txt" ps -A -o USER,PID,PPID,NAME,ARGS
  have logcat && safe_cmd "$d/android/logcat_dump.txt" logcat -d -v threadtime

  for f in "$HOME/.android/adbkey.pub" "$HOME/.android/adbkey"; do
    if [[ -r "$f" ]]; then
      printf '%s  %s\n' "$(sha "$f")" "$f" >>"$d/integrity/adb_local_key_hashes.txt"
    fi
  done
  if [[ -r /data/misc/adb/adb_keys ]]; then
    sha256sum /data/misc/adb/adb_keys >"$d/integrity/system_adb_keys.sha256" 2>&1 || true
  fi

  {
    printf '# CURRENT_SNAPSHOT_ONLY; NOT A TRUSTED BASELINE\n'
    find "$HOME" -xdev -type f \
      \( -name '*.sh' -o -name '*.py' -o -name '*.js' -o -name '*.json' -o -name '*.toml' \) \
      -size -16M -print0 2>/dev/null \
      | sort -z | xargs -0 -r sha256sum 2>/dev/null
  } >"$d/integrity/current_code_snapshot.sha256"

  printf '%s\n' "$(ts)" >"$d/meta/acquisition_finished_utc.txt"

  (
    cd "$d"
    find . -type f ! -name SHA256SUMS.txt -print0 \
      | sort -z | xargs -0 sha256sum > SHA256SUMS.txt
  )
  local manifest_hash
  manifest_hash="$(sha "$d/SHA256SUMS.txt")"
  printf '%s  SHA256SUMS.txt\n' "$manifest_hash" >"$d/SHA256SUMS.txt.sha256"

  verify_run "$d" || die "new run failed self-verification"

  local archive="$BASE/${run_id}.tar.gz"
  tar -C "$RUNS" -czf "$archive" "$run_id"
  chmod 400 "$archive" || true
  local archive_hash
  archive_hash="$(sha "$archive")"
  printf '%s  %s\n' "$archive_hash" "$(basename "$archive")" >"$archive.sha256"
  chmod 400 "$archive.sha256" || true

  append_ledger "$run_id" "$manifest_hash" "$archive_hash"
  protect_run "$d"

  printf '%s\n' "$run_id" >"$STATE/latest_run_id"
  printf '%s\n' "$archive" >"$STATE/latest_archive"

  if [[ "${FROST_EXPORT_SEALED:-0}" == "1" ]]; then
    mkdir -p "$EXPORT_DIR"
    cp -p "$archive" "$archive.sha256" "$LEDGER" "$EXPORT_DIR/"
  fi

  printf 'COLLECTION_PASS\nrun_id=%s\narchive=%s\narchive_sha256=%s\n' \
    "$run_id" "$archive" "$archive_hash"
}

status() {
  init_dirs
  printf '%s v%s\n' "$APP" "$VERSION"
  printf 'base=%s\n' "$BASE"
  printf 'runtime_class=%s\n' "$(runtime_class)"
  printf 'claim_scope=%s\n' "$(claim_scope)"
  printf 'runs=%s\n' "$(find "$RUNS" -mindepth 1 -maxdepth 1 -type d | wc -l)"
  [[ -f "$STATE/latest_run_id" ]] && printf 'latest_run=%s\n' "$(cat "$STATE/latest_run_id")"
  [[ -d "$LOCK" ]] && printf 'collector_lock=present\n' || printf 'collector_lock=clear\n'
  if verify_all >/dev/null 2>&1; then
    printf 'sealed_evidence=PASS\n'
  else
    printf 'sealed_evidence=FAIL\n'
  fi
}

install() {
  init_dirs
  local self
  self="$(readlink -f "$0")"
  mkdir -p "$HOME/.local/bin" "$HOME/.termux/boot"
  cp "$self" "$HOME/.local/bin/frost-physical-evidence-guardian"
  chmod 700 "$HOME/.local/bin/frost-physical-evidence-guardian"

  cat >"$BOOT" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -u
export PATH="\$HOME/.local/bin:\$PATH"
if command -v termux-wake-lock >/dev/null 2>&1; then termux-wake-lock >/dev/null 2>&1 || true; fi
nohup "\$HOME/.local/bin/frost-physical-evidence-guardian" daemon \
  >>"\$HOME/.frost_sentinel/physical_evidence/guardian.log" 2>&1 &
EOF
  chmod 700 "$BOOT"

  printf 'INSTALL_PASS\n'
  printf 'boot_hook=%s\n' "$BOOT"
  printf 'collector=%s\n' "$HOME/.local/bin/frost-physical-evidence-guardian"
  if [[ "$(runtime_class)" == "ANDROID_TERMUX" ]]; then
    printf 'Run "frost-physical-evidence-guardian collect" for a device-origin acquisition.\n'
  else
    printf 'Installation/collection here can validate software behavior. Device-origin claims require Android/Termux execution, but project qualification does not.\n'
  fi
}

daemon() {
  init_dirs
  while :; do
    collect || true
    sleep "$INTERVAL"
  done
}

case "${1:-collect}" in
  collect|once) collect ;;
  verify) verify_all ;;
  status) status ;;
  install) install ;;
  daemon) daemon ;;
  *)
    cat <<EOF
$APP v$VERSION
Usage: $0 {collect|verify|status|install|daemon}

collect  Perform one private logical acquisition; provenance scope is recorded automatically.
verify   Verify all sealed run manifests; fails if any retained run changed.
status   Show collector and evidence-integrity state.
install  Install a Termux:Boot persistent local collector (no remote control).
daemon   Collect periodically; interval defaults to 21600 seconds.

Environment:
  CASE_ID, OPERATOR
  FROST_EVIDENCE_HOME
  FROST_INTERVAL_SECONDS
  FROST_EXPORT_SEALED=1
  FROST_EXPORT_DIR

Validation and security model:
  - Validation is claim-scoped; there is no project-wide physical-device gate.
  - HOST_OR_SESSION may fully validate software logic, sealing, replay, deterministic behavior, and failure handling.
  - ANDROID_FIXTURE may additionally validate Android-specific parsing/collection logic against controlled fixtures.
  - ANDROID_TERMUX is required only for claims that evidence originated from a specific live handset or depends on live handset state.
  - Collects into private storage first and never overwrites prior runs.
  - Verifies prior sealed evidence before adding a new run; stops on detected prior-evidence modification.
  - Current code hashes are a snapshot, NOT a trusted-clean baseline.
  - This is logical acquisition, not physical/block imaging or write blocking.
  - No remote shell, credential capture, PIN guessing, exploit, or destructive action.
EOF
    exit 2
    ;;
esac
