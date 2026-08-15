#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${HOME}/automation-os-github-control-repo"
CFGDIR="${HOME}/.automation_os_github"
STATE="${CFGDIR}/state"
CANONICAL_REPO="12ephods-source/centinal26"
REPO="${AUTOMATION_OS_GITHUB_REPO:-$CANONICAL_REPO}"
DEVICE_ID="android-$(uname -m)-$(date +%s)"

[ "$REPO" = "$CANONICAL_REPO" ] || {
  echo "BLOCKED_NONCANONICAL_REPO $REPO" >&2
  exit 64
}

pkg update -y
pkg install -y gh git curl jq unzip coreutils python

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

rm -rf "$ROOT"
git clone "https://github.com/${REPO}.git" "$ROOT"
cd "$ROOT"
git checkout main
git pull --ff-only origin main

mkdir -p "$STATE"
chmod 700 "$CFGDIR" "$STATE"
# Runtime metadata is serialized as JSON data. Authentication remains in gh's
# credential store and is fetched on demand by the trusted runtime helper.
# Remove the legacy executable config only after the repository/helper is present.
# shellcheck disable=SC1091
source "$ROOT/termux/github_runtime_config.sh"
github_runtime_write_config "$CFGDIR/config.json" "$REPO" "main" "$DEVICE_ID"
rm -f "$CFGDIR/config"

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

echo "GitHub control worker installed from $REPO main."
echo "Expected physical artifact: ~/storage/downloads/AUTOMATION_OS_1.0.0_RC9_VALIDATION_INTEGRITY_PATCH.zip"
echo "Attempting immediate claim of the queued Automation OS device job..."
set +e
bash "$ROOT/termux/github_termux_worker_once.sh"
rc=$?
set -e

echo "Immediate worker return code: $rc"
if [ -f "$HOME/.automation_os_ga/state.json" ]; then
  jq '.' "$HOME/.automation_os_ga/state.json" || true
fi
exit "$rc"
