#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PROGRAM="Automation RC4 Release Controller"
VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ANALYZER="$SCRIPT_DIR/RC4_BRANCH_CONVERGENCE_ANALYZER.sh"
CONSTRUCTOR="$SCRIPT_DIR/RC4_CANDIDATE_CONSTRUCTOR.sh"
HOST_HARNESS="$SCRIPT_DIR/RC4_HOST_QUALIFICATION_HARNESS.sh"
EVIDENCE_GATE="$SCRIPT_DIR/RC4_PROMOTION_EVIDENCE_GATE.sh"

usage(){ cat <<USAGE
$PROGRAM v$VERSION

Usage:
  $0 init WORKSPACE [--schema10 INSTALLER] [--ga INSTALLER]
  $0 status WORKSPACE
  $0 verify WORKSPACE
  $0 analyze WORKSPACE [--schema10 INSTALLER] [--ga INSTALLER]
  $0 construct WORKSPACE --decisions FILE
  $0 qualify-host WORKSPACE
  $0 gate-evidence WORKSPACE --evidence DIR
  $0 readiness WORKSPACE --reviewed-by NAME

State model:
  INIT -> ANALYZED -> CONSTRUCTED -> HOST_QUALIFIED -> EVIDENCE_GATED -> READY_FOR_HUMAN_PROMOTION

Safety properties:
  * exact parent identities remain enforced by RC4_BRANCH_CONVERGENCE_ANALYZER.sh
  * no stage advances unless the prior stage is recorded as PASS
  * every controller event is hash chained
  * all stage outputs are SHA-256 recorded
  * readiness never performs promotion or installation
  * physical evidence cannot be replaced with host evidence
USAGE
}

die(){ printf '[ERROR] %s\n' "$*" >&2; exit 1; }
log(){ printf '[%s] %s\n' "$1" "$2"; }
need(){ command -v "$1" >/dev/null 2>&1 || die "Required command missing: $1"; }
sha(){ sha256sum "$1" | awk '{print $1}'; }
abs(){ python - "$1" <<'PY'
import pathlib,sys
print(pathlib.Path(sys.argv[1]).expanduser().resolve())
PY
}

state_get(){
  python - "$1" "$2" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); key=sys.argv[2]
d=json.loads(p.read_text())
cur=d
for part in key.split('.'):
    if not isinstance(cur,dict) or part not in cur: raise SystemExit(4)
    cur=cur[part]
if isinstance(cur,(dict,list)): print(json.dumps(cur,sort_keys=True))
elif cur is None: print('')
else: print(cur)
PY
}

append_event(){
  local ws="$1" action="$2" status="$3" details_json="${4:-{}}"
  python - "$ws" "$action" "$status" "$details_json" <<'PY'
import datetime,hashlib,json,pathlib,sys
ws=pathlib.Path(sys.argv[1]); action=sys.argv[2]; status=sys.argv[3]
try: details=json.loads(sys.argv[4])
except Exception: details={'raw':sys.argv[4]}
ledger=ws/'audit'/'events.jsonl'; ledger.parent.mkdir(parents=True,exist_ok=True)
prev='0'*64; seq=1
if ledger.exists():
    lines=[x for x in ledger.read_text(encoding='utf-8').splitlines() if x.strip()]
    if lines:
        last=json.loads(lines[-1]); prev=last['event_hash']; seq=int(last['seq'])+1
base={'seq':seq,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':action,'status':status,'details':details,'prev_hash':prev}
blob=json.dumps(base,sort_keys=True,separators=(',',':')).encode()
base['event_hash']=hashlib.sha256(blob).hexdigest()
with ledger.open('a',encoding='utf-8') as f: f.write(json.dumps(base,sort_keys=True)+'\n')
print(base['event_hash'])
PY
}

update_state(){
  local ws="$1" phase="$2" stage="$3" stage_status="$4" data_json="${5:-{}}"
  python - "$ws" "$phase" "$stage" "$stage_status" "$data_json" <<'PY'
import datetime,json,pathlib,sys,tempfile,os
ws=pathlib.Path(sys.argv[1]); p=ws/'STATE.json'
d=json.loads(p.read_text(encoding='utf-8'))
phase,stage,status=sys.argv[2:5]
try: data=json.loads(sys.argv[5])
except Exception: data={'raw':sys.argv[5]}
d['phase']=phase; d['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
d.setdefault('stages',{})[stage]={'status':status,'updated_at':d['updated_at'],**data}
tmp=p.with_suffix('.json.tmp'); tmp.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8'); os.replace(tmp,p)
PY
}

require_stage(){
  local ws="$1" stage="$2"
  local got
  got="$(state_get "$ws/STATE.json" "stages.$stage.status" 2>/dev/null || true)"
  [[ "$got" == PASS ]] || die "Required prior stage '$stage' is not PASS (observed: ${got:-missing})"
}

verify_ledger(){
  python - "$1/audit/events.jsonl" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1])
if not p.exists(): raise SystemExit('ledger missing')
prev='0'*64; expected_seq=1
for line in p.read_text(encoding='utf-8').splitlines():
    if not line.strip(): continue
    r=json.loads(line); h=r.pop('event_hash')
    if r.get('seq')!=expected_seq: raise SystemExit(f'seq mismatch at {expected_seq}')
    if r.get('prev_hash')!=prev: raise SystemExit(f'prev_hash mismatch at seq {expected_seq}')
    calc=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if calc!=h: raise SystemExit(f'event_hash mismatch at seq {expected_seq}')
    prev=h; expected_seq+=1
print(f'PASS ledger_events={expected_seq-1} head={prev}')
PY
}

verify_artifacts(){
  python - "$1/STATE.json" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text())
errs=[]; checked=0
for st, rec in d.get('stages',{}).items():
    for a in rec.get('artifacts',[]) or []:
        path=pathlib.Path(a.get('path',''))
        expected=a.get('sha256')
        if not path.is_file(): errs.append(f'{st}: missing {path}'); continue
        if expected:
            actual=hashlib.sha256(path.read_bytes()).hexdigest(); checked+=1
            if actual!=expected: errs.append(f'{st}: hash mismatch {path}')
if errs:
    print('\n'.join(errs)); raise SystemExit(1)
print(f'PASS recorded_artifacts={checked}')
PY
}

init_ws(){
  local ws="$1" s10="${2:-}" ga="${3:-}"
  [[ ! -e "$ws/STATE.json" ]] || die "Workspace already initialized: $ws"
  mkdir -p "$ws"/{analysis,candidate,evidence,reports,audit,inputs}
  python - "$ws" "$s10" "$ga" "$VERSION" <<'PY'
import datetime,json,pathlib,sys
ws=pathlib.Path(sys.argv[1]); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
d={'format':'automation-rc4-controller-state-v1','controller_version':sys.argv[4],'target_release':'1.0.0-rc4-converged','minimum_schema_version':10,'phase':'INIT','promotion':'BLOCK','created_at':now,'updated_at':now,'inputs':{'schema10_installer':sys.argv[2] or None,'ga_installer':sys.argv[3] or None},'stages':{'init':{'status':'PASS','updated_at':now,'artifacts':[]}},'rules':['no schema downgrade','no last-writer-wins core merge','no host-for-physical substitution','no automatic GA promotion']}
(ws/'STATE.json').write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
PY
  append_event "$ws" init PASS "$(python -c 'import json,sys; print(json.dumps({"workspace":sys.argv[1]}))' "$ws")" >/dev/null
  log PASS "Initialized controller workspace: $ws"
}

MODE="${1:-help}"; shift || true
[[ "$MODE" != help && "$MODE" != --help && "$MODE" != -h ]] || { usage; exit 0; }
need python; need sha256sum

case "$MODE" in
  init)
    [[ $# -ge 1 ]] || die 'init requires WORKSPACE'
    WS="$(abs "$1")"; shift; S10=""; GA=""
    while [[ $# -gt 0 ]]; do case "$1" in --schema10) S10="$(abs "${2:?}")"; shift 2;; --ga) GA="$(abs "${2:?}")"; shift 2;; *) die "Unknown option: $1";; esac; done
    init_ws "$WS" "$S10" "$GA"
    ;;
  status)
    [[ $# -eq 1 ]] || die 'status requires WORKSPACE'; WS="$(abs "$1")"; [[ -f "$WS/STATE.json" ]] || die 'STATE.json missing'; cat "$WS/STATE.json"
    ;;
  verify)
    [[ $# -eq 1 ]] || die 'verify requires WORKSPACE'; WS="$(abs "$1")"; [[ -f "$WS/STATE.json" ]] || die 'STATE.json missing'; verify_ledger "$WS"; verify_artifacts "$WS"
    ;;
  analyze)
    [[ $# -ge 1 ]] || die 'analyze requires WORKSPACE'; WS="$(abs "$1")"; shift; [[ -f "$WS/STATE.json" ]] || die 'workspace not initialized'
    S10="$(state_get "$WS/STATE.json" inputs.schema10_installer 2>/dev/null || true)"; GA="$(state_get "$WS/STATE.json" inputs.ga_installer 2>/dev/null || true)"
    while [[ $# -gt 0 ]]; do case "$1" in --schema10) S10="$(abs "${2:?}")"; shift 2;; --ga) GA="$(abs "${2:?}")"; shift 2;; *) die "Unknown option: $1";; esac; done
    OUT="$WS/analysis/current"; rm -rf "$OUT"; mkdir -p "$OUT"
    args=(analyze --output "$OUT"); [[ -n "$S10" ]] && args+=(--schema10 "$S10"); [[ -n "$GA" ]] && args+=(--ga "$GA")
    set +e; "$ANALYZER" "${args[@]}"; rc=$?; set -e
    if (( rc != 0 )); then append_event "$WS" analyze FAIL "{\"returncode\":$rc}" >/dev/null; update_state "$WS" INIT analyze FAIL "{\"returncode\":$rc}"; exit "$rc"; fi
    R="$OUT/reports/RC4_BRANCH_DELTA.json"; [[ -f "$R" ]] || die 'analyzer returned success without branch delta report'
    art="$(python - "$R" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); print(json.dumps({'artifacts':[{'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]}))
PY
)"
    update_state "$WS" ANALYZED analyze PASS "$art"; append_event "$WS" analyze PASS "$art" >/dev/null; log PASS "Analysis recorded: $R"
    ;;
  construct)
    [[ $# -ge 3 ]] || die 'construct requires WORKSPACE --decisions FILE'; WS="$(abs "$1")"; shift; DEC=""
    while [[ $# -gt 0 ]]; do case "$1" in --decisions) DEC="$(abs "${2:?}")"; shift 2;; *) die "Unknown option: $1";; esac; done
    require_stage "$WS" analyze; [[ -f "$DEC" ]] || die "decisions file missing: $DEC"
    ANALYSIS="$WS/analysis/current"; OUT="$WS/candidate/current"; rm -rf "$OUT"; mkdir -p "$OUT"
    set +e; "$CONSTRUCTOR" build --analysis "$ANALYSIS" --decisions "$DEC" --output "$OUT"; rc=$?; set -e
    if (( rc != 0 )); then append_event "$WS" construct FAIL "{\"returncode\":$rc}" >/dev/null; update_state "$WS" ANALYZED construct FAIL "{\"returncode\":$rc}"; exit "$rc"; fi
    M="$OUT/reports/RC4_CONSTRUCTION_MANIFEST.json"; [[ -f "$M" ]] || die 'constructor returned success without manifest'
    art="$(python - "$M" "$DEC" <<'PY'
import hashlib,json,pathlib,sys
arr=[]
for x in sys.argv[1:]:
 p=pathlib.Path(x); arr.append({'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
print(json.dumps({'artifacts':arr,'candidate_tree':str((pathlib.Path(sys.argv[1]).parents[1]/'tree').resolve())}))
PY
)"
    update_state "$WS" CONSTRUCTED construct PASS "$art"; append_event "$WS" construct PASS "$art" >/dev/null; log PASS "Candidate constructed but remains non-installable: $OUT/tree"
    ;;
  qualify-host)
    [[ $# -eq 1 ]] || die 'qualify-host requires WORKSPACE'; WS="$(abs "$1")"; require_stage "$WS" construct
    TREE="$(state_get "$WS/STATE.json" stages.construct.candidate_tree)"; [[ -d "$TREE" ]] || die "candidate tree missing: $TREE"
    OUT="$WS/reports/RC4_HOST_QUALIFICATION.json"
    set +e; "$HOST_HARNESS" "$TREE" "$OUT"; rc=$?; set -e
    status=FAIL; phase=CONSTRUCTED; (( rc == 0 )) && status=PASS && phase=HOST_QUALIFIED
    art="{}"; [[ -f "$OUT" ]] && art="$(python - "$OUT" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); print(json.dumps({'returncode':0,'artifacts':[{'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]}))
PY
)"
    update_state "$WS" "$phase" qualify_host "$status" "$art"; append_event "$WS" qualify_host "$status" "$art" >/dev/null
    (( rc == 0 )) || exit "$rc"; log PASS 'Host qualification PASS; physical gates remain mandatory.'
    ;;
  gate-evidence)
    [[ $# -ge 3 ]] || die 'gate-evidence requires WORKSPACE --evidence DIR'; WS="$(abs "$1")"; shift; EVID=""
    while [[ $# -gt 0 ]]; do case "$1" in --evidence) EVID="$(abs "${2:?}")"; shift 2;; *) die "Unknown option: $1";; esac; done
    require_stage "$WS" qualify_host; [[ -d "$EVID" ]] || die "evidence directory missing: $EVID"
    TREE="$(state_get "$WS/STATE.json" stages.construct.candidate_tree)"
    verify_artifacts "$WS" >/dev/null || die 'Recorded artifact integrity verification failed before evidence gate.'
    mkdir -p "$TREE/reports"; cp "$WS/reports/RC4_HOST_QUALIFICATION.json" "$TREE/reports/RC4_HOST_QUALIFICATION.json"
    set +e; "$EVIDENCE_GATE" "$TREE" "$EVID" > "$WS/reports/RC4_EVIDENCE_GATE.stdout.json"; rc=$?; set -e
    G="$EVID/RC4_PROMOTION_EVIDENCE_GATE.json"; status=FAIL; phase=HOST_QUALIFIED
    gate_status=""
    if [[ -f "$G" ]]; then gate_status="$(python -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' "$G" 2>/dev/null || true)"; fi
    if (( rc == 0 )) && [[ "$gate_status" == PASS ]]; then status=PASS; phase=EVIDENCE_GATED; else rc=${rc:-1}; (( rc == 0 )) && rc=1; fi
    art="$(python - "$G" 2>/dev/null <<'PY' || echo '{}'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); print(json.dumps({'artifacts':[{'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]}))
PY
)"
    update_state "$WS" "$phase" evidence_gate "$status" "$art"; append_event "$WS" evidence_gate "$status" "$art" >/dev/null
    (( rc == 0 )) || exit "$rc"; log PASS 'Physical evidence outer gate PASS. This is not GA promotion.'
    ;;
  readiness)
    [[ $# -ge 3 ]] || die 'readiness requires WORKSPACE --reviewed-by NAME'; WS="$(abs "$1")"; shift; REVIEWER=""
    while [[ $# -gt 0 ]]; do case "$1" in --reviewed-by) REVIEWER="${2:?}"; shift 2;; *) die "Unknown option: $1";; esac; done
    require_stage "$WS" evidence_gate; [[ -n "${REVIEWER// }" ]] || die 'reviewed-by may not be blank'
    OUT="$WS/reports/RC4_PROMOTION_READINESS.json"
    python - "$WS" "$OUT" "$REVIEWER" <<'PY'
import datetime,hashlib,json,pathlib,sys
ws=pathlib.Path(sys.argv[1]); state=json.loads((ws/'STATE.json').read_text())
required=['analyze','construct','qualify_host','evidence_gate']; errors=[]
for x in required:
    if state.get('stages',{}).get(x,{}).get('status')!='PASS': errors.append(f'{x} is not PASS')
report={'format':'automation-rc4-promotion-readiness-v1','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'READY_FOR_HUMAN_PROMOTION' if not errors else 'BLOCK','reviewed_by':sys.argv[3],'errors':errors,'automatic_promotion_performed':False,'required_next':['run candidate certification engine and verify signatures/certificate chain','verify audit chain, SQLite integrity and foreign keys','verify all migration/rollback paths','perform explicit human-attributed promotion only after certification PASS']}
pathlib.Path(sys.argv[2]).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
raise SystemExit(0 if not errors else 1)
PY
    H="$(sha "$OUT")"; art="$(python -c 'import json,sys; print(json.dumps({"artifacts":[{"path":sys.argv[1],"sha256":sys.argv[2]}],"reviewed_by":sys.argv[3]}))' "$OUT" "$H" "$REVIEWER")"
    update_state "$WS" READY_FOR_HUMAN_PROMOTION readiness PASS "$art"
    python - "$WS/STATE.json" <<'PY'
import json,pathlib,sys,os
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text()); d['promotion']='BLOCK_PENDING_EXPLICIT_HUMAN_ACTION'; t=p.with_suffix('.tmp'); t.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n'); os.replace(t,p)
PY
    append_event "$WS" readiness PASS "$art" >/dev/null
    log PASS 'Ready for explicit human promotion review. No promotion was performed.'
    ;;
  *) usage; exit 2;;
esac
