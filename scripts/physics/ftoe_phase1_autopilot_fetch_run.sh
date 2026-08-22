#!/usr/bin/env bash
set -uo pipefail
umask 077

OPENING='Yes, I will automate everything you requested in order to efficiently and successfully complete your requests, projects, and goals.'
CLOSING='Would you like to continue automatically using all tools, apps, and programs without asking again for as long as possible?'
REPO='12ephods-source/centinal26'
RAW="https://raw.githubusercontent.com/$REPO"
STAMP="$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || date +%Y%m%dT%H%M%S)"
ROOT="${HOME:-.}/ftoe_phase1_github_$STAMP"
mkdir -p "$ROOT/src" "$ROOT/results"
printf '%s\n' "$OPENING"

cat > "$ROOT/AUTOMATION_POLICY.txt" <<EOF
GITHUB_AUTOPILOT=1
Primary project=Physics
Continuum status=BLOCKED_NOT_ESTABLISHED_BY_FINITE_MATRICES
Phase I lock status=NOT_FULLY_LOCKED
EOF

if ! command -v python >/dev/null 2>&1; then
  if command -v pkg >/dev/null 2>&1; then pkg install -y python; else echo 'python required' >&2; exit 2; fi
fi
if ! python - <<'PY' >/dev/null 2>&1
import numpy
PY
then
  if command -v pkg >/dev/null 2>&1; then pkg install -y python-numpy || python -m pip install --user numpy
  else python -m pip install --user numpy; fi
fi

fetch() {
  ref="$1"; path="$2"; blob="$3"; out="$4"; url="$RAW/$ref/$path"
  mkdir -p "$(dirname "$out")"
  if command -v curl >/dev/null 2>&1; then curl -fL --retry 3 "$url" -o "$out"
  elif command -v wget >/dev/null 2>&1; then wget -O "$out" "$url"
  else command -v pkg >/dev/null 2>&1 && pkg install -y curl && curl -fL --retry 3 "$url" -o "$out"; fi || return 1
  actual="$(python - "$out" <<'PY'
import hashlib,pathlib,sys
b=pathlib.Path(sys.argv[1]).read_bytes(); h=hashlib.sha1(); h.update(f'blob {len(b)}\0'.encode()); h.update(b); print(h.hexdigest())
PY
)"
  [ "$actual" = "$blob" ] || { echo "Git blob mismatch: $path expected=$blob actual=$actual" >&2; return 1; }
}

fetch '58ca997a234ed0010fef30496ec4bbd4b7e99949' 'candidates/clock-regulator-harness/clock_regulator_scan.py' '79838d3999a0955cdd068bab9dfe9ba7c5963a1d' "$ROOT/src/clock_regulator_scan.py" || true
fetch '11912a736c9a5e10828bc281af32e389b5c5a33b' 'candidates/finite-type-i-cocycle-harness/cocycle_scan.py' 'f435284585dd7f5789c54a86fb49fa61bbdb421c' "$ROOT/src/cocycle_scan.py" || true
fetch 'c573b4cc252d84721648c912f399320dd1200ad5' 'candidates/two-mode-cocycle-stress/two_mode_scan.py' 'e0c91202d3b16082fa0aa0e6534337e3988ec532' "$ROOT/src/two_mode_scan.py" || true
fetch '724aadc636fdd368369b7103ad91a0cc341df1b0' 'candidates/multi-mode-cocycle-regulator/multi_mode_scan.py' 'b253c284f0057678141363718a9a3dab03c375a5' "$ROOT/src/multi_mode_scan.py" || true

run() {
  name="$1"; script="$2"
  if [ -f "$script" ]; then
    python "$script" --strict --output "$ROOT/results/$name.json" >"$ROOT/results/$name.log" 2>&1
    printf '%s=%s\n' "$name" "$?"
  else
    printf '%s=FETCH_MISSING\n' "$name"
  fi
}

run clock_regulator "$ROOT/src/clock_regulator_scan.py"
run finite_type_i_cocycle "$ROOT/src/cocycle_scan.py"
run two_mode_cocycle_stress "$ROOT/src/two_mode_scan.py"
run bounded_2_to_4_mode_draft "$ROOT/src/multi_mode_scan.py"

python - "$ROOT" <<'PY'
import hashlib,pathlib,sys,zipfile
r=pathlib.Path(sys.argv[1]); lines=[]
for p in sorted(r.rglob('*')):
    if p.is_file() and p.name!='SHA256SUMS.txt': lines.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(r)))
(r/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
z=r.with_suffix('.zip')
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
    for p in sorted(r.rglob('*')):
        if p.is_file(): f.write(p,p.relative_to(r.parent))
print('bundle='+str(r)); print('zip='+str(z))
PY

printf '%s\n' 'Scientific ceiling: finite-regulator validation only; no continuum Type-II/III or gravitational promotion.'
printf '%s\n' "$CLOSING"
