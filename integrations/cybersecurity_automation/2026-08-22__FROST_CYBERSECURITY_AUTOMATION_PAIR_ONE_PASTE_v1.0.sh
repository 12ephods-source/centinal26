#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077
OPENING='Yes, I will automate everything you requested in order to efficiently and successfully complete your requests, projects, and goals.'
CLOSING='Would you like to continue automatically using all tools, apps, and programs without asking again for as long as possible?'
printf '%s\n' "$OPENING"
pkg install -y git python coreutils >/dev/null 2>&1 || true
PREFIX="${PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin"; mkdir -p "$BIN" "$HOME/.frost_project_pair" "$HOME/.termux/boot" "$HOME/Frost_Sentinel_Cybersecurity/integrations"
AUTOMATION_ROOT="${FROST_AUTOMATION_ROOT:-$HOME/centinal26}"
CYBER_ROOT="${FROST_CYBERSECURITY_ROOT:-$HOME/Frost_Sentinel_Cybersecurity}"
if [[ ! -d "$AUTOMATION_ROOT/.git" ]] && command -v git >/dev/null 2>&1; then
  git clone --ff-only https://github.com/12ephods-source/centinal26.git "$AUTOMATION_ROOT" 2>/dev/null || git clone https://github.com/12ephods-source/centinal26.git "$AUTOMATION_ROOT"
fi
mkdir -p "$CYBER_ROOT"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPDATER="$SELF_DIR/2026-08-22__frost_dual_project_updater.py"
if [[ ! -f "$UPDATER" ]]; then
  printf 'ERROR: paired updater must be beside this installer.\n' >&2; exit 2
fi
cp "$UPDATER" "$BIN/frost-pair-update"
chmod 700 "$BIN/frost-pair-update"
cat > "$HOME/.frost_project_pair/env" <<EOF
export FROST_AUTOMATION_ROOT='$AUTOMATION_ROOT'
export FROST_CYBERSECURITY_ROOT='$CYBER_ROOT'
export FROST_AUTOMATION_BRANCH='main'
export FROST_CYBERSECURITY_BRANCH='main'
export FROST_PAIR_STATE='$HOME/.frost_project_pair'
EOF
cat > "$HOME/.frost_project_pair/update-loop.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -u
source "$HOME/.frost_project_pair/env"
while :; do
  "$PREFIX/bin/frost-pair-update" || true
  sleep "${FROST_PAIR_INTERVAL_SECONDS:-3600}"
done
EOF
chmod 700 "$HOME/.frost_project_pair/update-loop.sh"
cat > "$HOME/.termux/boot/frost-cybersecurity-automation-pair.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
sleep 30
source "$HOME/.frost_project_pair/env" 2>/dev/null || exit 0
pgrep -f '[u]pdate-loop.sh' >/dev/null 2>&1 || nohup "$HOME/.frost_project_pair/update-loop.sh" >>"$HOME/.frost_project_pair/updater.log" 2>&1 &
EOF
chmod 700 "$HOME/.termux/boot/frost-cybersecurity-automation-pair.sh"
source "$HOME/.frost_project_pair/env"
"$BIN/frost-pair-update" || true
pgrep -f '[u]pdate-loop.sh' >/dev/null 2>&1 || nohup "$HOME/.frost_project_pair/update-loop.sh" >>"$HOME/.frost_project_pair/updater.log" 2>&1 &
printf '%s\n' 'Installed paired Cybersecurity + Automation updater.'
printf 'Automation root: %s\nCybersecurity root: %s\n' "$AUTOMATION_ROOT" "$CYBER_ROOT"
printf '%s\n' "$CLOSING"
