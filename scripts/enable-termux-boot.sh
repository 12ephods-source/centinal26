#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
boot_dir="$HOME/.termux/boot"
mkdir -p "$boot_dir"
install -m 700 "$repo_root/deploy/termux/centinal26-boot.sh" "$boot_dir/centinal26.sh"
printf 'Installed Termux:Boot hook: %s\n' "$boot_dir/centinal26.sh"
printf 'The hook starts the bounded Centinal26 daemon after Android boot when Termux:Boot is installed.\n'
