#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="${FTOE_REPO_URL:-https://github.com/12ephods-source/centinal26.git}"
BRANCH="${FTOE_BRANCH:-agent/ftoe-research-orchestrator-v10}"
ROOT="${FTOE_ROOT:-$HOME/centinal26}"
SERVICE="$PREFIX/var/service/ftoe-research"
CONFIG_DIR="$HOME/.config/ftoe-research"
SECRETS_FILE="$CONFIG_DIR/providers.secrets"
RUNTIME_FILE="$CONFIG_DIR/runtime.env"

pkg update -y
pkg install -y python git curl jq termux-services
mkdir -p "$CONFIG_DIR" "$HOME/.termux/boot"

if [ ! -d "$ROOT/.git" ]; then
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$ROOT"
else
  git -C "$ROOT" fetch origin "$BRANCH"
  git -C "$ROOT" checkout "$BRANCH"
  git -C "$ROOT" merge --ff-only "origin/$BRANCH"
fi

if [ ! -f "$SECRETS_FILE" ]; then
cat > "$SECRETS_FILE" <<'EOF'
# Literal KEY=VALUE only. This file is parsed, never sourced/eval'd.
# Add only providers you actually use; leave others absent.
# OPENAI_API_KEY=
# OPENAI_MODEL=
# ANTHROPIC_API_KEY=
# ANTHROPIC_MODEL=
# GEMINI_API_KEY=
# GEMINI_MODEL=
# XAI_API_KEY=
# XAI_MODEL=
# DEEPSEEK_API_KEY=
# DEEPSEEK_MODEL=
# MISTRAL_API_KEY=
# MISTRAL_MODEL=
# COHERE_API_KEY=
# COHERE_MODEL=
EOF
chmod 600 "$SECRETS_FILE"
fi

if [ ! -f "$RUNTIME_FILE" ]; then
cat > "$RUNTIME_FILE" <<'EOF'
FTOE_AGENT_INTERVAL=3600
FTOE_MAX_LLM_CALLS_PER_CYCLE=5
EOF
chmod 600 "$RUNTIME_FILE"
fi

mkdir -p "$SERVICE/log" "$HOME/.local/state/ftoe-research-log"
cat > "$SERVICE/run" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
# Runtime settings are non-secret. Provider secrets are NOT sourced into this process.
if [ -f "$RUNTIME_FILE" ]; then
  while IFS='=' read -r key value; do
    case "\$key" in
      FTOE_AGENT_INTERVAL|FTOE_MAX_LLM_CALLS_PER_CYCLE) export "\$key=\$value" ;;
    esac
  done < "$RUNTIME_FILE"
fi
export FTOE_PROVIDER_SECRETS="$SECRETS_FILE"
cd "$ROOT"
exec python scripts/ftoe_secure_supervisor.py --interval "\${FTOE_AGENT_INTERVAL:-3600}" 2>&1
EOF
chmod 700 "$SERVICE/run"

cat > "$SERVICE/log/run" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
exec svlogd -tt "$HOME/.local/state/ftoe-research-log"
EOF
chmod 700 "$SERVICE/log/run"

cat > "$HOME/.termux/boot/ftoe-research-start.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock || true
sv up ftoe-research || true
EOF
chmod 700 "$HOME/.termux/boot/ftoe-research-start.sh"

sv-enable ftoe-research || true
sv up ftoe-research || true

echo "Installed split-authority FToE research supervisor."
echo "Provider secrets: $SECRETS_FILE (mode 600; parsed only by one-shot broker)"
echo "Runtime config: $RUNTIME_FILE"
echo "Status: sv status ftoe-research"
echo "Logs: tail -f $HOME/.local/state/ftoe-research-log/current"
echo "One-shot: cd $ROOT && FTOE_PROVIDER_SECRETS=$SECRETS_FILE python scripts/ftoe_secure_supervisor.py --once"
echo "Security note: supervisor and broker share the same Termux/Android UID; this is process separation, not hard OS sandboxing."
