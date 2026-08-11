#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

PROGRAM="RC4 exact-parent recovery"
SCHEMA10_SHA="e21ed868d11ec7525a0fba54e58854b00a9fd151681a1efc26ffd9cf202f40d2"
SCHEMA10_PAYLOAD_SHA="79e53364ff0462dadf9b1d454123791c0db26d0a860bda98cf3e788183106e0a"
SCHEMA10_SIZE=844877
GA_SHA="cfd2e3e285550b2d4f995a7edf10377ca983276da9b79e16084e0a36b040e7d7"
GA_PAYLOAD_SHA="692c59e891d5f539933c363563b1256b10c225d15878598724b9b6cca03c8f58"
GA_SIZE=278935
OUT="${FROST_RC4_PARENT_DIR:-$HOME/automation-rc4-parent-inputs}"
REPORT="$OUT/PARENT_RECOVERY_REPORT.json"
SUMS="$OUT/SHA256SUMS.txt"

log(){ printf '[%s] %s\n' "$1" "$2"; }
die(){ log ERROR "$*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || die "Required command missing: $1"; }
sha(){ sha256sum "$1" | awk '{print $1}'; }
size(){ wc -c < "$1" | tr -d '[:space:]'; }

for cmd in python sha256sum find cp sort; do need "$cmd"; done
mkdir -p "$OUT"
chmod 700 "$OUT" 2>/dev/null || true

unique_roots(){
  python - "$HOME" <<'PY_ROOTS'
import pathlib, sys
home = pathlib.Path(sys.argv[1])
roots = [
    home / "storage/downloads",
    home / "storage/shared/Download",
    home / "storage/shared/Documents",
    pathlib.Path("/sdcard/Download"),
    pathlib.Path("/storage/emulated/0/Download"),
    home / "Downloads",
    home,
]
seen = set()
for path in roots:
    try:
        resolved = str(path.resolve())
    except Exception:
        resolved = str(path)
    if resolved not in seen and pathlib.Path(resolved).exists():
        seen.add(resolved)
        print(resolved)
PY_ROOTS
}

find_exact_hash(){
  local want="$1" f h
  while IFS= read -r root; do
    while IFS= read -r -d '' f; do
      h="$(sha "$f" 2>/dev/null || true)"
      [[ "$h" == "$want" ]] && printf '%s\n' "$f"
    done < <(find "$root" -maxdepth 4 -type f \
      \( -name 'install_automation_platform*.sh' -o -name '*rc3*.sh' \) \
      -size -8M -print0 2>/dev/null)
  done < <(unique_roots)
}

select_exact(){
  local want="$1" expected_size="$2" label="$3" matches selected actual_size
  matches="$(find_exact_hash "$want" | sort -u)"
  [[ -n "$matches" ]] || die "$label exact parent not found (wanted $want)"
  selected="$(printf '%s\n' "$matches" | head -n1)"
  actual_size="$(size "$selected")"
  [[ "$actual_size" == "$expected_size" ]] || die "$label size mismatch: expected $expected_size got $actual_size"
  printf '%s\n' "$selected"
}

extract_payload(){
  local installer="$1" expected="$2" output="$3"
  python - "$installer" "$output" <<'PY_PAYLOAD'
import base64, pathlib, re, sys
source = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
text = source.read_text(encoding="utf-8")
lines = text.splitlines()
start = None
marker = "PAYLOAD_B64"
for i, line in enumerate(lines):
    if re.search(r"<<['\"]?PAYLOAD_B64['\"]?", line):
        start = i + 1
        break
if start is None:
    raise SystemExit("PAYLOAD_B64 heredoc start not found")
end = None
for i in range(start, len(lines)):
    if lines[i].strip() == marker:
        end = i
        break
if end is None:
    raise SystemExit("PAYLOAD_B64 heredoc terminator not found")
encoded = "".join(line.strip() for line in lines[start:end] if line.strip())
try:
    payload = base64.b64decode(encoded, validate=True)
except Exception as exc:
    raise SystemExit(f"invalid embedded base64 payload: {exc}") from exc
out.write_bytes(payload)
PY_PAYLOAD
  local actual
  actual="$(sha "$output")"
  [[ "$actual" == "$expected" ]] || { rm -f "$output"; die "payload hash mismatch for $installer: expected $expected got $actual"; }
}

log INFO "Searching readable Termux/shared-storage roots for exact pinned RC3 parents."
SCHEMA10_SRC="$(select_exact "$SCHEMA10_SHA" "$SCHEMA10_SIZE" schema10)"
GA_SRC="$(select_exact "$GA_SHA" "$GA_SIZE" ga)"

SCHEMA10_DST="$OUT/rc3-device-validation-schema10.sh"
GA_DST="$OUT/rc3-ga-campaign-schema9.sh"
SCHEMA10_PAYLOAD="$OUT/schema10-embedded-payload.tar.gz"
GA_PAYLOAD="$OUT/ga-embedded-payload.tar.gz"

cp -p "$SCHEMA10_SRC" "$SCHEMA10_DST"
cp -p "$GA_SRC" "$GA_DST"
[[ "$(sha "$SCHEMA10_DST")" == "$SCHEMA10_SHA" ]] || die "schema10 copy hash mismatch"
[[ "$(sha "$GA_DST")" == "$GA_SHA" ]] || die "GA copy hash mismatch"

log INFO "Decoding embedded payloads without executing either installer."
extract_payload "$SCHEMA10_DST" "$SCHEMA10_PAYLOAD_SHA" "$SCHEMA10_PAYLOAD"
extract_payload "$GA_DST" "$GA_PAYLOAD_SHA" "$GA_PAYLOAD"

python - "$REPORT" "$SCHEMA10_SRC" "$GA_SRC" "$SCHEMA10_DST" "$GA_DST" "$SCHEMA10_PAYLOAD" "$GA_PAYLOAD" <<'PY_REPORT'
import datetime, hashlib, json, pathlib, sys
report, s10_src, ga_src, s10_dst, ga_dst, s10_payload, ga_payload = map(pathlib.Path, sys.argv[1:])

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def record(path):
    return {"path": str(path), "sha256": digest(path), "size_bytes": path.stat().st_size}

data = {
    "format": "automation-rc4-parent-recovery-report-v1",
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "status": "PASS",
    "operation": "hash-verified discovery, copy, and embedded-payload extraction only",
    "installers_executed": False,
    "parents": {
        "schema10_device_validation": {
            "source_path": str(s10_src),
            "copied": record(s10_dst),
            "payload": record(s10_payload),
        },
        "schema9_ga_campaign": {
            "source_path": str(ga_src),
            "copied": record(ga_dst),
            "payload": record(ga_payload),
        },
    },
    "release_claims": {
        "semantic_convergence_reviewed": False,
        "candidate_constructed": False,
        "host_qualified": False,
        "physical_android_validated": False,
        "promotion_performed": False,
    },
    "next_gate": "run the RC4 convergence analyzer against these two verified parent copies",
}
report.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY_REPORT

(
  cd "$OUT"
  sha256sum \
    rc3-device-validation-schema10.sh \
    rc3-ga-campaign-schema9.sh \
    schema10-embedded-payload.tar.gz \
    ga-embedded-payload.tar.gz \
    PARENT_RECOVERY_REPORT.json > SHA256SUMS.txt
)

log PASS "Exact RC3 parents and embedded payloads recovered and hash-verified."
log PASS "Report: $REPORT"
log PASS "Checksums: $SUMS"
