#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

ROOT="${AUTOMATION_OS_ROOT:-$HOME/AutomationOS}"
REF="${FROST_AUTOMATION_REF:-2bbd048f57b7b4edb3b3b2935248316dd086c649}"
RAW="https://raw.githubusercontent.com/12ephods-source/centinal26/$REF"
MGR_SHA256="b94aa37821d326c167b8f1b27f9f1a3a53732e1d189f73e0ebb32fdd5f2216ac"
REG_SHA256="4dc840d8215e5d52a385f1d4d7f0ffeaa478df65a411f8f91762e4885893ffc3"

say(){ printf '[automation-os-v3] %s\n' "$*"; }
die(){ printf '[automation-os-v3] ERROR: %s\n' "$*" >&2; exit 1; }

case "${PREFIX:-}" in *com.termux*) ;; *) die "Run this inside Termux on Android.";; esac
pkg update -y
pkg install -y python curl coreutils git jq sqlite

mkdir -p "$ROOT"/{bin,registry,state,cache,modules,logs,projects}
curl -fsSL "$RAW/deploy/automation_os/module_manager.py" -o "$ROOT/bin/module_manager.py"
curl -fsSL "$RAW/deploy/automation_os/registry.json" -o "$ROOT/registry/registry.json"

echo "$MGR_SHA256  $ROOT/bin/module_manager.py" | sha256sum -c -
echo "$REG_SHA256  $ROOT/registry/registry.json" | sha256sum -c -
python -m py_compile "$ROOT/bin/module_manager.py"

mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/frost-install" <<EOF
#!/usr/bin/env bash
exec python "$ROOT/bin/module_manager.py" "\$@"
EOF
chmod 700 "$HOME/.local/bin/frost-install" "$ROOT/bin/module_manager.py"

AUTOMATION_OS_ROOT="$ROOT" python "$ROOT/bin/module_manager.py" self-test

say "Framework installed. Use: frost-install list"
say "To install the canonical Android fleet: frost-install install android-fleet"
