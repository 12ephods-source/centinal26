import re
import subprocess
from pathlib import Path

V151 = Path("deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.1.sh")
V17 = Path("deploy/termux/FROST_FLEET_BOOTSTRAP_v1.7.sh")


def test_v151_separates_path_assignment_before_out_expansion():
    text = V151.read_text(encoding="utf-8")
    assert 'local commit="$1" path="$2" expected_blob="$3" out=' not in text
    assert 'local path="$2"\n  local expected_blob="$3"\n  local out="$TMP_ROOT/$(basename "$path")"' in text


def test_v151_fetch_helper_executes_under_nounset_without_network(tmp_path):
    text = V151.read_text(encoding="utf-8")
    match = re.search(r"fetch_verify_run\(\)\{\n(?P<body>.*?)\n\}", text, re.DOTALL)
    assert match, "fetch_verify_run helper not found"
    helper = "fetch_verify_run(){\n" + match.group("body") + "\n}"

    program = f'''set -Eeuo pipefail
TMP_ROOT={str(tmp_path)!r}
REPO_RAW=https://example.invalid

die() {{ printf '%s\\n' "$*" >&2; exit 1; }}
verify_git_blob() {{ :; }}
curl() {{
  local out=""
  while (($#)); do
    if [[ "$1" == "-o" ]]; then out="$2"; shift 2; else shift; fi
  done
  printf '#!/usr/bin/env bash\\nexit 0\\n' > "$out"
}}
{helper}
fetch_verify_run deadbeef deploy/termux/example.sh expected
'''
    result = subprocess.run(
        ["bash", "-c", program], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_v17_pins_fixed_v151_and_keeps_reboot_disabled():
    text = V17.read_text(encoding="utf-8")
    assert 'BASE_COMMIT="fdad8cdab27471e6192abc423707bf5cebd4d449"' in text
    assert 'BASE_PATH="deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.1.sh"' in text
    assert 'BASE_BLOB="23d2b4c9f3648642eb7ad5a9d93da51db9d05d56"' in text
    assert "device.validation.ensure" in text
    assert "device.validation.verify" in text
    assert "remote Android reboot: disabled" in text
    assert "arbitrary remote shell: disabled" in text
