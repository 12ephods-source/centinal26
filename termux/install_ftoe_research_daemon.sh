#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="${FTOE_REPO_URL:-https://github.com/12ephods-source/centinal26.git}"
BRANCH="${FTOE_BRANCH:-agent/ftoe-research-orchestrator-v10}"
ROOT="${FTOE_ROOT:-$HOME/centinal26}"
SERVICE="$PREFIX/var/service/ftoe-research"
ENV_FILE="$HOME/.config/ftoe-research/providers.env"

pkg update -y
pkg install -y python git curl jq termux-services
mkdir -p "$HOME/.config/ftoe-research" "$HOME/.termux/boot"

if [ ! -d "$ROOT/.git" ]; then
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$ROOT"
else
  git -C "$ROOT" fetch origin "$BRANCH"
  git -C "$ROOT" checkout "$BRANCH"
  git -C "$ROOT" merge --ff-only "origin/$BRANCH"
fi

if [ ! -f "$ENV_FILE" ]; then
cat > "$ENV_FILE" <<'EOF'
# Add only the providers you have accounts/keys for. Leave others unset.
# Never commit this file.
# OPENAI_API_KEY=
# OPENAI_MODEL=gpt-5
# ANTHROPIC_API_KEY=
# ANTHROPIC_MODEL=claude-fable-5
# GEMINI_API_KEY=
# GEMINI_MODEL=gemini-3.6-flash
# XAI_API_KEY=
# XAI_MODEL=grok-4.5
# DEEPSEEK_API_KEY=
# DEEPSEEK_MODEL=deepseek-v4-pro
# MISTRAL_API_KEY=
# MISTRAL_MODEL=mistral-large-latest
# COHERE_API_KEY=
# COHERE_MODEL=command-a-plus-05-2026
FTOE_AGENT_INTERVAL=3600
EOF
chmod 600 "$ENV_FILE"
fi

mkdir -p "$SERVICE/log"
cat > "$SERVICE/run" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
[ -f "$ENV_FILE" ] && set -a && source "$ENV_FILE" && set +a
cd "$ROOT"
exec python scripts/ftoe_research_daemon.py --interval "\${FTOE_AGENT_INTERVAL:-3600}" 2>&1
EOF
chmod 700 "$SERVICE/run"

cat > "$SERVICE/log/run" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
exec svlogd -tt "$HOME/.local/state/ftoe-research-log"
EOF
mkdir -p "$HOME/.local/state/ftoe-research-log"
chmod 700 "$SERVICE/log/run"

cat > "$HOME/.termux/boot/ftoe-research-start.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock || true
sv up ftoe-research || true
EOF
chmod 700 "$HOME/.termux/boot/ftoe-research-start.sh"

sv-enable ftoe-research || true
sv up ftoe-research || true

echo "Installed FToE research daemon."
echo "Configure API keys: $ENV_FILE"
echo "Status: sv status ftoe-research"
echo "Logs: tail -f $HOME/.local/state/ftoe-research-log/current"
echo "One-shot: cd $ROOT && set -a && source $ENV_FILE && set +a && python scripts/ftoe_research_daemon.py --once"
