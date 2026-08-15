#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
CFGDIR="${HOME}/.automation_os_github"
REPO="${AUTOMATION_OS_GITHUB_REPO:-12ephods-source/centinal26}"

mkdir -p "$CFGDIR" "$HOME/.termux/boot" "$HOME/.automation_intelligence_gate"
chmod 700 "$CFGDIR" "$HOME/.automation_intelligence_gate"

# Reuse an already provisioned token/device identity before touching the package manager.
if [ -f "$CFGDIR/config" ]; then
  # shellcheck disable=SC1090
  source "$CFGDIR/config"
fi
TOKEN="${GITHUB_TOKEN:-}"
DEVICE_ID="${AUTOMATION_DEVICE_ID:-android-$(uname -m)-$(date +%s)}"

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
if [ -z "$TOKEN" ]; then
  need_package gh gh
fi

if [ "${#missing_packages[@]}" -gt 0 ]; then
  command -v pkg >/dev/null 2>&1 || {
    echo "BLOCKED_TERMUX_PACKAGES: pkg unavailable; missing: ${missing_packages[*]}" >&2
    exit 3
  }
  # Do not run `pkg update` unconditionally. A working existing environment must remain usable
  # even when a configured mirror/key is temporarily unhealthy. Install only missing commands.
  if ! pkg install -y "${missing_packages[@]}"; then
    echo "BLOCKED_TERMUX_PACKAGES: missing commands could not be installed: ${missing_packages[*]}" >&2
    echo "Existing tools and evidence were left unchanged." >&2
    exit 3
  fi
fi

if [ -z "$TOKEN" ]; then
  if gh auth status --hostname github.com >/dev/null 2>&1; then
    echo "GITHUB_AUTH: EXISTING_LOGIN"
  else
    gh auth login --hostname github.com --web --git-protocol https --scopes repo,workflow
  fi
  gh auth setup-git --hostname github.com
  TOKEN="$(gh auth token --hostname github.com)"
fi
[ -n "$TOKEN" ] || { echo "BLOCKED_GITHUB_AUTH" >&2; exit 2; }

if [ -d "$ROOT/.git" ]; then
  git -C "$ROOT" fetch origin main
  git -C "$ROOT" checkout main
  git -C "$ROOT" pull --ff-only origin main
else
  git clone "https://github.com/${REPO}.git" "$ROOT"
fi

cat > "$CFGDIR/config" <<EOF_CFG
GITHUB_REPO="$REPO"
GITHUB_TOKEN="$TOKEN"
GITHUB_REF="main"
AUTOMATION_DEVICE_ID="$DEVICE_ID"
EOF_CFG
chmod 600 "$CFGDIR/config"

python -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -e "$ROOT"

cat > "$HOME/.termux/boot/centinal26-intelligence-controller.sh" <<EOF_BOOT
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
sleep 20
export CENTINAL26_REPO_ROOT="$ROOT"
export CENTINAL26_VENV="$ROOT/.venv"
export CENTINAL26_HOME="$HOME/.local/state/centinal26"
export AUTOMATION_DEVICE_ID="$DEVICE_ID"
"$ROOT/termux/intelligence_controller_supervisor.sh" boot >> "$HOME/.automation_intelligence_gate/boot.log" 2>&1
EOF_BOOT
chmod 700 "$HOME/.termux/boot/centinal26-intelligence-controller.sh"

cat > "$HOME/.termux/boot/centinal26-intelligence-job.sh" <<EOF_JOB
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
sleep 60
export CENTINAL26_REPO_ROOT="$ROOT"
bash "$ROOT/termux/intelligence_controller_github_worker_once.sh" >> "$HOME/.automation_intelligence_gate/worker_boot.log" 2>&1
EOF_JOB
chmod 700 "$HOME/.termux/boot/centinal26-intelligence-job.sh"

cat > "$HOME/.termux/boot/centinal26-intelligence-report.sh" <<EOF_REPORT
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
sleep 120
export CENTINAL26_REPO_ROOT="$ROOT"
bash "$ROOT/termux/intelligence_controller_report_after_reboot.sh" >> "$HOME/.automation_intelligence_gate/report_boot.log" 2>&1
EOF_REPORT
chmod 700 "$HOME/.termux/boot/centinal26-intelligence-report.sh"

echo "Centinal26 intelligence control installed for device $DEVICE_ID."
echo "Attempting immediate claim of open intelligence-controller physical-gate job..."
set +e
CENTINAL26_REPO_ROOT="$ROOT" bash "$ROOT/termux/intelligence_controller_github_worker_once.sh"
rc=$?
set -e
if [ "$rc" -eq 0 ]; then
  echo "Worker completed its current non-reboot phase."
else
  echo "Worker returned rc=$rc; inspect ~/.automation_intelligence_gate/." >&2
fi
exit "$rc"
