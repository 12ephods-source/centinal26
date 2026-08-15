#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
CFGDIR="${HOME}/.automation_os_github"
REPO="${AUTOMATION_OS_GITHUB_REPO:-12ephods-source/centinal26}"

pkg update -y
pkg install -y gh git curl jq coreutils python procps

if gh auth status --hostname github.com >/dev/null 2>&1; then
  echo "GITHUB_AUTH: EXISTING_LOGIN"
else
  gh auth login --hostname github.com --web --git-protocol https --scopes repo,workflow
fi
gh auth setup-git --hostname github.com
TOKEN="$(gh auth token --hostname github.com)"
[ -n "$TOKEN" ] || { echo "BLOCKED_GITHUB_AUTH"; exit 2; }

if [ -d "$ROOT/.git" ]; then
  git -C "$ROOT" fetch origin main
  git -C "$ROOT" checkout main
  git -C "$ROOT" pull --ff-only origin main
else
  git clone "https://github.com/${REPO}.git" "$ROOT"
fi

mkdir -p "$CFGDIR" "$HOME/.termux/boot" "$HOME/.automation_intelligence_gate"
chmod 700 "$CFGDIR" "$HOME/.automation_intelligence_gate"
if [ -f "$CFGDIR/config" ]; then
  # Preserve an existing device identifier while refreshing credentials and repository.
  # shellcheck disable=SC1090
  source "$CFGDIR/config"
fi
DEVICE_ID="${AUTOMATION_DEVICE_ID:-android-$(uname -m)-$(date +%s)}"
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
echo "Attempting immediate claim of an open intelligence-controller physical-gate job..."
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
