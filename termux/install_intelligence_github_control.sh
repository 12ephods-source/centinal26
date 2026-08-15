#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
CFGDIR="${HOME}/.automation_os_github"
CANONICAL_REPO="12ephods-source/centinal26"
REPO="${AUTOMATION_OS_GITHUB_REPO:-$CANONICAL_REPO}"
GATE_ROOT="$HOME/.automation_intelligence_gate"

[ "$REPO" = "$CANONICAL_REPO" ] || {
  echo "BLOCKED_NONCANONICAL_REPO $REPO" >&2
  exit 64
}

mkdir -p "$CFGDIR" "$HOME/.termux/boot" "$GATE_ROOT"
chmod 700 "$CFGDIR" "$GATE_ROOT"

missing_packages=()
need_package() {
  local command_name="$1" package_name="$2"
  command -v "$command_name" >/dev/null 2>&1 || missing_packages+=("$package_name")
}
need_package git git
need_package curl curl
need_package jq jq
need_package sha256sum coreutils
need_package python python
need_package pgrep procps
need_package gh gh

if [ "${#missing_packages[@]}" -gt 0 ]; then
  command -v pkg >/dev/null 2>&1 || {
    echo "BLOCKED_TERMUX_PACKAGES: pkg unavailable; missing: ${missing_packages[*]}" >&2
    exit 3
  }
  if ! pkg install -y "${missing_packages[@]}"; then
    echo "BLOCKED_TERMUX_PACKAGES: missing commands could not be installed: ${missing_packages[*]}" >&2
    echo "Existing tools and evidence were left unchanged." >&2
    exit 3
  fi
fi

if gh auth status --hostname github.com >/dev/null 2>&1; then
  echo "GITHUB_AUTH: EXISTING_LOGIN"
else
  gh auth login --hostname github.com --web --git-protocol https --scopes repo,workflow
fi
gh auth setup-git --hostname github.com
[ -n "$(gh auth token --hostname github.com 2>/dev/null || true)" ] || {
  echo "BLOCKED_GITHUB_AUTH" >&2
  exit 2
}

if [ -d "$ROOT/.git" ]; then
  [ -z "$(git -C "$ROOT" status --porcelain)" ] || {
    echo "BLOCKED_LOCAL_CHANGES: refusing to overwrite local repository changes." >&2
    exit 4
  }
  git -C "$ROOT" fetch origin main
  git -C "$ROOT" checkout main
  git -C "$ROOT" merge --ff-only origin/main
else
  git clone "https://github.com/${REPO}.git" "$ROOT"
fi

RUNTIME_CONFIG="$ROOT/termux/github_runtime_config.sh"
[ -f "$RUNTIME_CONFIG" ] || { echo "Missing runtime config helper: $RUNTIME_CONFIG" >&2; exit 2; }
# Preserve a valid prior device identity from data-only config; never execute config content.
DEVICE_ID=""
if [ -f "$CFGDIR/config.json" ]; then
  DEVICE_ID="$(jq -r 'select(.schema == "centinal26-github-worker-config-v1" and .github_repo == "12ephods-source/centinal26") | .automation_device_id // empty' "$CFGDIR/config.json" 2>/dev/null || true)"
fi
if ! [[ "$DEVICE_ID" =~ ^[A-Za-z0-9._:-]{1,128}$ ]]; then
  DEVICE_ID="android-$(uname -m)-$(date +%s)"
fi
# shellcheck disable=SC1090
source "$RUNTIME_CONFIG"
github_runtime_write_config "$CFGDIR/config.json" "$REPO" "main" "$DEVICE_ID"
rm -f "$CFGDIR/config"

python -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -e "$ROOT"

NODE="$ROOT/termux/intelligence_node.sh"
chmod 700 \
  "$NODE" \
  "$ROOT/termux/intelligence_controller_supervisor.sh" \
  "$ROOT/termux/intelligence_controller_github_worker_once.sh" \
  "$ROOT/termux/intelligence_controller_report_after_reboot.sh" \
  "$ROOT/termux/intelligence_controller_physical_gate.sh" \
  "$ROOT/termux/automation_project_finalizer.sh" \
  "$ROOT/termux/intelligence_node_endurance.sh" \
  "$ROOT/termux/verify_project_finalization.py" \
  "$ROOT/deploy/termux/recover-rc4-parent-inputs.sh"

cat > "$HOME/.termux/boot/centinal26-intelligence-controller.sh" <<EOF_BOOT
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
sleep 20
export CENTINAL26_REPO_ROOT="$ROOT"
export CENTINAL26_VENV="$ROOT/.venv"
export CENTINAL26_HOME="$HOME/.local/state/centinal26"
export AUTOMATION_DEVICE_ID="$DEVICE_ID"
"$NODE" boot >> "$GATE_ROOT/boot.log" 2>&1
EOF_BOOT
chmod 700 "$HOME/.termux/boot/centinal26-intelligence-controller.sh"

cat > "$HOME/.termux/boot/centinal26-intelligence-job.sh" <<EOF_JOB
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
sleep 60
export CENTINAL26_REPO_ROOT="$ROOT"
export CENTINAL26_VENV="$ROOT/.venv"
export AUTOMATION_DEVICE_ID="$DEVICE_ID"
"$NODE" kick >> "$GATE_ROOT/worker_boot.log" 2>&1
EOF_JOB
chmod 700 "$HOME/.termux/boot/centinal26-intelligence-job.sh"

cat > "$HOME/.termux/boot/centinal26-intelligence-report.sh" <<EOF_REPORT
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
sleep 120
export CENTINAL26_REPO_ROOT="$ROOT"
export CENTINAL26_VENV="$ROOT/.venv"
export AUTOMATION_DEVICE_ID="$DEVICE_ID"
bash "$ROOT/termux/intelligence_controller_report_after_reboot.sh" >> "$GATE_ROOT/report_boot.log" 2>&1
EOF_REPORT
chmod 700 "$HOME/.termux/boot/centinal26-intelligence-report.sh"

echo "Centinal26 Termux node v2 + Automation v1 finalizer installed for device $DEVICE_ID."
"$NODE" start >/dev/null
"$NODE" doctor

echo "Attempting immediate bounded finalization claim..."
set +e
"$NODE" kick
rc=$?
set -e
if [ "$rc" -eq 0 ]; then
  echo "Node completed its current non-reboot phase."
else
  echo "Node kick returned rc=$rc; watchdog remains installed and will retry with bounded backoff. Inspect $GATE_ROOT." >&2
fi
exit 0
