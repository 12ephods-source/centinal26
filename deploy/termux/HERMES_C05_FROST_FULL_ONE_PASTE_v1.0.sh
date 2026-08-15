#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

VERSION="1.0.0"
ADAPTER_COMMIT="34e8b49dd7d5858081081f2e729921047cdbdc2b"
REPO="https://github.com/12ephods-source/centinal26.git"
HERMES_INSTALL_URL="https://hermes-agent.nousresearch.com/install.sh"
RECOVERED_BASE_NAME="hermes_frost_hybrid_termux_monolith_v2_0_0_2026-07-30.sh"
RECOVERED_PAYLOAD_SHA="c23d8a1004df13eccfa2fec82835f2bce1274d2aed92a633df49734ca51aef8a"
CERTIFIED_SHELL_SHA="322e16d78b8eeb0940e0083f69e9d3720b3b2f383715d9cc180e60ff40c44df9"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
APP_DIR="$DATA_HOME/hermes-c05"
C05_DIR="$DATA_HOME/frost-c05/centinal26"
C05_VENV="$DATA_HOME/frost-c05/venv"
STATE_DIR="$STATE_HOME/hermes-c05"
CENTINAL26_HOME="${CENTINAL26_HOME:-$STATE_HOME/centinal26}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_DIR="$HERMES_HOME/plugins/frost_orchestrator"
WORKSPACE="$HERMES_HOME/frost_orchestrator"
BIN_DIR="$HOME/.local/bin"
BRIDGE="$APP_DIR/hermes_c05_bridge.py"
LOCK_DIR="$STATE_DIR/install.lock"
STAMP="$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || date +%Y%m%dT%H%M%S)"
RECEIPT="$STATE_DIR/receipts/$STAMP"
MODE="install"
ENABLE_BOOT=1
SETUP_STORAGE=1
SKIP_HERMES=0
SKIP_RECOVERED=0

usage() {
  cat <<EOF
HERMES + C05 Frost Agent Fabric — complete one-paste installer v$VERSION

Usage:
  bash HERMES_C05_FROST_FULL_ONE_PASTE_v1.0.sh
  bash HERMES_C05_FROST_FULL_ONE_PASTE_v1.0.sh --self-test
  bash HERMES_C05_FROST_FULL_ONE_PASTE_v1.0.sh --doctor

Options:
  --self-test             Validate the installed/source integration without modifying it.
  --doctor                Run installed diagnostics.
  --skip-hermes           Do not install Hermes when absent.
  --skip-recovered-base   Do not search for the recovered v2 monolith.
  --no-storage            Skip termux-setup-storage.
  --no-boot               Skip the bounded Termux:Boot hook.
  -h, --help              Show help.

Pinned adapter source:
  $ADAPTER_COMMIT

Architecture:
  HERMES -> reasoning / model-provider coordination / MoA / relay
  C05    -> authorization / durable execution / independent verification / audit
EOF
}

while (($#)); do
  case "$1" in
    --self-test) MODE="self-test" ;;
    --doctor) MODE="doctor" ;;
    --skip-hermes) SKIP_HERMES=1 ;;
    --skip-recovered-base) SKIP_RECOVERED=1 ;;
    --no-storage) SETUP_STORAGE=0 ;;
    --no-boot) ENABLE_BOOT=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

say() { printf '[hermes-c05] %s\n' "$*"; }
warn() { printf '[hermes-c05] WARNING: %s\n' "$*" >&2; }
die() { printf '[hermes-c05] ERROR: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

sha256_file() {
  if have sha256sum; then
    sha256sum "$1" | awk '{print $1}'
  elif have shasum; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    python - "$1" <<'PY'
import hashlib, sys
h = hashlib.sha256()
with open(sys.argv[1], "rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(block)
print(h.hexdigest())
PY
  fi
}

is_termux() {
  [[ -n "${TERMUX_VERSION:-}" ]] || [[ "${PREFIX:-}" == "/data/data/com.termux/files/usr" ]]
}

failure_receipt() {
  local rc="$1"
  [[ "$MODE" == "install" ]] || return 0
  mkdir -p "$RECEIPT" 2>/dev/null || true
  cat > "$RECEIPT/FAILURE.txt" <<EOF
result=FAIL
stage=${STAGE:-unknown}
exit_code=$rc
timestamp_utc=$(date -u +%FT%TZ 2>/dev/null || true)
adapter_commit=$ADAPTER_COMMIT
EOF
}

cleanup() {
  local rc=$?
  rmdir "$LOCK_DIR" 2>/dev/null || true
  (( rc == 0 )) || failure_receipt "$rc"
  trap - EXIT INT TERM
  exit "$rc"
}
trap cleanup EXIT INT TERM

setup_layout() {
  mkdir -p "$APP_DIR" "$STATE_DIR" "$RECEIPT" "$BIN_DIR" "$WORKSPACE"
}

install_packages() {
  is_termux || die "Full installation must run inside Termux"
  have pkg || die "Termux pkg is unavailable"
  pkg update -y
  pkg install -y python git curl coreutils openssl nodejs
}

install_hermes() {
  if have hermes; then
    say "Preserving existing Hermes at $(command -v hermes)"
    return 0
  fi
  (( SKIP_HERMES == 0 )) || die "Hermes is absent and --skip-hermes was requested"
  local installer
  installer="$(mktemp)"
  curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \
    "$HERMES_INSTALL_URL" -o "$installer"
  say "Official Hermes installer SHA-256: $(sha256_file "$installer")"
  bash "$installer"
  rm -f "$installer"
  export PATH="$HOME/.local/bin:$PATH"
  have hermes || die "Hermes installation completed but hermes is not on PATH"
}

find_recovered_base() {
  local candidate
  for candidate in \
    "$PWD/$RECOVERED_BASE_NAME" \
    "$HOME/storage/downloads/$RECOVERED_BASE_NAME" \
    "$HOME/downloads/$RECOVERED_BASE_NAME" \
    "$HOME/Downloads/$RECOVERED_BASE_NAME"
  do
    [[ -f "$candidate" ]] || continue
    printf '%s\n' "$candidate"
    return 0
  done
  return 1
}

use_recovered_base() {
  RECOVERED_STATUS="NOT_MATERIALIZED"
  RECOVERED_SHELL_SHA=""
  (( SKIP_RECOVERED == 0 )) || { RECOVERED_STATUS="SKIPPED"; return 0; }

  local base marker
  if ! base="$(find_recovered_base)"; then
    warn "Recovered HERMES v2 monolith not found in common Downloads paths."
    return 0
  fi

  marker="$(grep -F 'readonly PAYLOAD_SHA256="' "$base" | head -n1 || true)"
  [[ "$marker" == *"$RECOVERED_PAYLOAD_SHA"* ]] ||
    die "Recovered v2 payload identity mismatch"

  RECOVERED_SHELL_SHA="$(sha256_file "$base")"
  if [[ "$RECOVERED_SHELL_SHA" == "$CERTIFIED_SHELL_SHA" ]]; then
    RECOVERED_STATUS="CERTIFIED_SHELL_MATCH"
  else
    RECOVERED_STATUS="PAYLOAD_MATCH_SHELL_UNCERTIFIED"
    warn "Recovered payload identity matches, but the whole shell differs from the certified candidate."
  fi

  bash "$base" --self-test
  bash "$base" --install --skip-hermes
}

install_c05_source() {
  local fresh="$C05_DIR.new.$STAMP"
  rm -rf "$fresh"
  git clone --filter=blob:none --no-tags "$REPO" "$fresh"
  git -C "$fresh" fetch --no-tags origin "$ADAPTER_COMMIT"
  git -C "$fresh" checkout --detach "$ADAPTER_COMMIT"
  [[ "$(git -C "$fresh" rev-parse HEAD)" == "$ADAPTER_COMMIT" ]] ||
    die "C05 adapter source identity mismatch"

  if [[ -e "$C05_DIR" ]]; then
    local backup="$DATA_HOME/frost-c05/backups/centinal26-$STAMP"
    mkdir -p "$(dirname "$backup")"
    mv "$C05_DIR" "$backup"
    say "Previous managed C05 source backed up to $backup"
  fi
  mv "$fresh" "$C05_DIR"

  rm -rf "$C05_VENV"
  python -m venv "$C05_VENV"
  "$C05_VENV/bin/python" -m pip install --upgrade pip setuptools wheel
  "$C05_VENV/bin/python" -m pip install -e "$C05_DIR[dev]"
}

install_adapter() {
  mkdir -p "$APP_DIR"
  cp "$C05_DIR/deploy/hermes-c05/hermes_c05_bridge.py" "$BRIDGE"
  chmod 700 "$BRIDGE"

  if [[ -d "$PLUGIN_DIR" ]]; then
    local archive="$WORKSPACE/migration_archives/frost_orchestrator-pre-c05-$STAMP"
    mkdir -p "$(dirname "$archive")"
    cp -a "$PLUGIN_DIR" "$archive"
    say "Prior Frost plugin archived to $archive"
  fi

  rm -rf "$PLUGIN_DIR"
  mkdir -p "$PLUGIN_DIR"
  cp -a "$C05_DIR/deploy/hermes-c05/plugin/frost_orchestrator/." "$PLUGIN_DIR/"
  chmod -R go-rwx "$PLUGIN_DIR"
}

install_wrappers() {
  cat > "$BIN_DIR/hermes-c05" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
export CENTINAL26_HOME="$CENTINAL26_HOME"
export HERMES_C05_HOME="$STATE_DIR"
export PYTHONPATH="$C05_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$C05_VENV/bin/python" "$BRIDGE" "\$@"
EOF

  cat > "$BIN_DIR/hermes-frost" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
export CENTINAL26_HOME="$CENTINAL26_HOME"
export HERMES_C05_HOME="$STATE_DIR"
export HERMES_C05_BRIDGE="$BRIDGE"
export PYTHONPATH="$C05_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}"
exec hermes "\$@"
EOF

  cat > "$BIN_DIR/hermes-frost-doctor" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
export CENTINAL26_HOME="$CENTINAL26_HOME"
export HERMES_C05_HOME="$STATE_DIR"
export PYTHONPATH="$C05_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}"
echo "=== HERMES ==="
hermes doctor || true
echo "=== C05 ==="
"$C05_VENV/bin/centinal26" status
echo "=== BRIDGE ==="
"$C05_VENV/bin/python" "$BRIDGE" status
"$C05_VENV/bin/python" "$BRIDGE" verify-audit
test -f "$PLUGIN_DIR/plugin.yaml"
test -f "$PLUGIN_DIR/__init__.py"
test -f "$PLUGIN_DIR/tools.py"
echo "DOCTOR PASS"
EOF

  chmod 700 "$BIN_DIR/hermes-c05" "$BIN_DIR/hermes-frost" "$BIN_DIR/hermes-frost-doctor"

  touch "$HOME/.bashrc"
  grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc" ||
    printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.bashrc"
}

install_boot() {
  (( ENABLE_BOOT == 1 )) || return 0
  mkdir -p "$HOME/.termux/boot" "$STATE_DIR/boot"
  cat > "$HOME/.termux/boot/hermes-c05-frost.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
export PATH="$BIN_DIR:\$PATH"
export CENTINAL26_HOME="$CENTINAL26_HOME"
{
  echo "boot_utc=\$(date -u +%FT%TZ 2>/dev/null || true)"
  "$BIN_DIR/hermes-c05" status
  "$C05_VENV/bin/centinal26" run-once
} >> "$STATE_DIR/boot/boot.log" 2>&1
EOF
  chmod 700 "$HOME/.termux/boot/hermes-c05-frost.sh"
}

run_validation() {
  export CENTINAL26_HOME="$CENTINAL26_HOME"
  export HERMES_C05_HOME="$STATE_DIR"
  export PYTHONPATH="$C05_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

  "$C05_VENV/bin/python" -m py_compile \
    "$BRIDGE" \
    "$PLUGIN_DIR/__init__.py" \
    "$PLUGIN_DIR/tools.py"
  "$C05_VENV/bin/centinal26" init
  "$C05_VENV/bin/centinal26" demo
  "$C05_VENV/bin/centinal26" status | tee "$RECEIPT/c05-status.json"
  "$C05_VENV/bin/python" "$BRIDGE" selftest | tee "$RECEIPT/bridge-selftest.json"
  "$C05_VENV/bin/python" "$BRIDGE" verify-audit
  "$C05_VENV/bin/python" -m pytest -q "$C05_DIR/tests/test_hermes_c05_adapter.py"
  "$C05_VENV/bin/python" -m ruff check \
    "$C05_DIR/deploy/hermes-c05" \
    "$C05_DIR/tests/test_hermes_c05_adapter.py"
}

seal_receipt() {
  cat > "$RECEIPT/receipt.json" <<EOF
{
  "schema": "frost-hermes-c05-install/1",
  "version": "$VERSION",
  "timestamp_utc": "$(date -u +%FT%TZ)",
  "adapter_commit": "$ADAPTER_COMMIT",
  "recovered_base_status": "$RECOVERED_STATUS",
  "recovered_shell_sha256": "$RECOVERED_SHELL_SHA",
  "recovered_payload_expected_sha256": "$RECOVERED_PAYLOAD_SHA",
  "direct_script_execution": "RETIRED",
  "model_callable_non_a0": false,
  "github_write_from_model": false,
  "validation": "PASS"
}
EOF

  (
    cd "$RECEIPT"
    : > SHA256SUMS.txt
    local file
    for file in *.json *.txt; do
      [[ -f "$file" && "$file" != "SHA256SUMS.txt" ]] || continue
      printf '%s  %s\n' "$(sha256_file "$file")" "$file" >> SHA256SUMS.txt
    done
    while read -r expected file; do
      [[ "$(sha256_file "$file")" == "$expected" ]] ||
        die "Receipt verification failed: $file"
    done < SHA256SUMS.txt
    sha256_file SHA256SUMS.txt > SHA256SUMS.txt.sha256
  )
}

self_test_source() {
  local source="$0"
  bash -n "$source"
  if [[ -f "$BRIDGE" && -x "$C05_VENV/bin/python" ]]; then
    export CENTINAL26_HOME="$CENTINAL26_HOME"
    export HERMES_C05_HOME="$STATE_DIR"
    export PYTHONPATH="$C05_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
    "$C05_VENV/bin/python" "$BRIDGE" selftest
    "$C05_VENV/bin/python" "$BRIDGE" verify-audit
  else
    say "Installer syntax PASS; installed bridge not present, so runtime self-test was not run."
  fi
}

doctor() {
  [[ -x "$BIN_DIR/hermes-frost-doctor" ]] || die "Installed doctor not found"
  "$BIN_DIR/hermes-frost-doctor"
}

main() {
  setup_layout

  case "$MODE" in
    self-test)
      self_test_source
      return
      ;;
    doctor)
      doctor
      return
      ;;
  esac

  mkdir "$LOCK_DIR" 2>/dev/null || die "Another HERMES/C05 installer is active"

  STAGE="packages"
  install_packages
  if (( SETUP_STORAGE == 1 )) && have termux-setup-storage; then
    termux-setup-storage || true
  fi

  STAGE="hermes"
  install_hermes

  STAGE="recovered-base"
  use_recovered_base

  STAGE="c05-source"
  install_c05_source

  STAGE="adapter"
  install_adapter

  STAGE="wrappers"
  install_wrappers

  STAGE="boot"
  install_boot

  STAGE="validation"
  run_validation

  STAGE="receipt"
  seal_receipt

  STAGE="complete"
  cat <<EOF

============================================================
 HERMES + C05 FROST INTEGRATION — INSTALL PASS
============================================================

Pinned adapter source:
  $ADAPTER_COMMIT

Recovered HERMES v2:
  status: $RECOVERED_STATUS
  shell SHA-256: $RECOVERED_SHELL_SHA
  expected payload SHA-256: $RECOVERED_PAYLOAD_SHA

Commands:
  hermes-frost
  hermes-c05 status
  hermes-c05 selftest
  hermes-frost-doctor

Inside Hermes:
  /frost-status
  /frost-call system.echo {"message":"hello"}
  /frost-relay <task>
  /frost-protocol

Direct /frost-approve script execution has been retired.
Non-A0 authorization remains a direct-user, single-use-token flow.
Connected GitHub calls are staged locally; the Hermes model path does not publish them.

Receipt:
  $RECEIPT
EOF
}

main "$@"
