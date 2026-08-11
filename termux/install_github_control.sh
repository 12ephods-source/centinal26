#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${HOME}/automation-os-github-control-repo"
CFGDIR="${HOME}/.automation_os_github"
STATE="${CFGDIR}/state"
REPO="${AUTOMATION_OS_GITHUB_REPO:-12ephods-source/centinal26}"

pkg update -y
pkg install -y gh git curl jq unzip coreutils python

if gh auth status --hostname github.com >/dev/null 2>&1; then
  echo "GITHUB_AUTH: EXISTING_LOGIN"
else
  gh auth login --hostname github.com --web --git-protocol https --scopes repo,workflow
fi

gh auth setup-git --hostname github.com
TOKEN="$(gh auth token --hostname github.com)"
[ -n "$TOKEN" ] || { echo "BLOCKED_GITHUB_AUTH"; exit 2; }

rm -rf "$ROOT"
git clone "https://github.com/${REPO}.git" "$ROOT"
cd "$ROOT"

git fetch origin agent/integrity-pinned-github-control
git checkout agent/integrity-pinned-github-control

mkdir -p "$STATE"
chmod 700 "$CFGDIR" "$STATE"
cat > "$CFGDIR/config" <<EOF
GITHUB_REPO="$REPO"
GITHUB_TOKEN="$TOKEN"
GITHUB_REF="agent/integrity-pinned-github-control"
AUTOMATION_DEVICE_ID="android-$(uname -m)-$(date +%s)"
EOF
chmod 600 "$CFGDIR/config"

mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/automation-os-github-worker.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
sleep 60
bash "${HOME}/automation-os-github-control-repo/termux/github_termux_worker_once.sh" >> "${HOME}/.automation_os_github/worker_boot.log" 2>&1
EOF
chmod 700 "$HOME/.termux/boot/automation-os-github-worker.sh"

cat > "$HOME/.termux/boot/automation-os-github-report.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
sleep 120
bash "${HOME}/automation-os-github-control-repo/termux/report_after_reboot.sh" >> "${HOME}/.automation_os_github/report_boot.log" 2>&1
EOF
chmod 700 "$HOME/.termux/boot/automation-os-github-report.sh"

echo "GitHub control worker installed from $REPO."
echo "Place AUTOMATION_OS_1.0.0_RC9_VALIDATION_INTEGRITY_PATCH.zip in ~/storage/downloads/ before dispatching the physical-GA workflow."
