#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PROGRAM="Automation RC4 Release Controller Successor"
VERSION="1.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYZER="$SCRIPT_DIR/RC4_BRANCH_CONVERGENCE_ANALYZER_SUCCESSOR.py"
CONSTRUCTOR="$SCRIPT_DIR/RC4_CANDIDATE_CONSTRUCTOR_SUCCESSOR.py"
HOST_HARNESS="$SCRIPT_DIR/RC4_HOST_QUALIFICATION_HARNESS_SUCCESSOR.py"
EVIDENCE_GATE="$SCRIPT_DIR/RC4_PROMOTION_EVIDENCE_GATE_SUCCESSOR.py"

usage(){ cat <<'USAGE'
Automation RC4 Release Controller Successor v1.1.0

This is a RECONSTRUCTED_SUCCESSOR, not the unrecovered original RC4 controller/toolchain.

Usage:
  RC4_RELEASE_CONTROLLER_SUCCESSOR.sh init WORKSPACE [--schema10 INSTALLER] [--ga INSTALLER]
  RC4_RELEASE_CONTROLLER_SUCCESSOR.sh status WORKSPACE
  RC4_RELEASE_CONTROLLER_SUCCESSOR.sh verify WORKSPACE
  RC4_RELEASE_CONTROLLER_SUCCESSOR.sh analyze WORKSPACE [--schema10 INSTALLER] [--ga INSTALLER]
  RC4_RELEASE_CONTROLLER_SUCCESSOR.sh construct WORKSPACE --decisions FILE
  RC4_RELEASE_CONTROLLER_SUCCESSOR.sh qualify-host WORKSPACE
  RC4_RELEASE_CONTROLLER_SUCCESSOR.sh gate-evidence WORKSPACE --evidence DIR
  RC4_RELEASE_CONTROLLER_SUCCESSOR.sh certify WORKSPACE --report FILE
  RC4_RELEASE_CONTROLLER_SUCCESSOR.sh readiness WORKSPACE --reviewed-by NAME

State model:
  INIT -> ANALYZED -> CONSTRUCTED -> HOST_QUALIFIED -> EVIDENCE_GATED -> CERTIFIED -> READY_FOR_HUMAN_PROMOTION

A readiness result never installs, tags, merges, releases, or promotes anything.
USAGE
}

die(){ printf '[ERROR] %s\n' "$*" >&2; exit 1; }
log(){ printf '[%s] %s\n' "$1" "$2"; }
need(){ command -v "$1" >/dev/null 2>&1 || die "Required command missing: $1"; }
abs(){ python - "$1" <<'PY'
import pathlib,sys
print(pathlib.Path(sys.argv[1]).expanduser().resolve())
PY
}
sha(){ sha256sum "$1" | awk '{print $1}'; }

state_get(){
  python - "$1" "$2" <<'PY'
import json,pathlib,sys
cur=json.loads(pathlib.Path(sys.argv[1]).read_text())
for part in sys.argv[2].split('.'):
    if not isinstance(cur,dict) or part not in cur: raise SystemExit(4)
    cur=cur[part]
if isinstance(cur,(dict,list)): print(json.dumps(cur,sort_keys=True))
elif cur is None: print('')
else: print(cur)
PY
}

append_event(){
  local ws="$1" action="$2" status="$3" details="${4:-{}}"
  python - "$ws" "$action" "$status" "$details" <<'PY'
import datetime,hashlib,json,pathlib,sys
ws=pathlib.Path(sys.argv[1]); ledger=ws/'audit'/'events.jsonl'; ledger.parent.mkdir(parents=True,exist_ok=True)
try: details=json.loads(sys.argv[4])
except Exception: details={'raw':sys.argv[4]}
prev='0'*64; seq=1
if ledger.exists():
    lines=[x for x in ledger.read_text().splitlines() if x.strip()]
    if lines:
        last=json.loads(lines[-1]); prev=last['event_hash']; seq=int(last['seq'])+1
base={'seq':seq,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':sys.argv[2],'status':sys.argv[3],'details':details,'prev_hash':prev}
base['event_hash']=hashlib.sha256(json.dumps(base,sort_keys=True,separators=(',',':')).encode()).hexdigest()
with ledger.open('a',encoding='utf-8') as f: f.write(json.dumps(base,sort_keys=True)+'\n')
PY
}

update_state(){
  local ws="$1" phase="$2" stage="$3" status="$4" data="${5:-{}}"
  python - "$ws" "$phase" "$stage" "$status" "$data" <<'PY'
import datetime,json,os,pathlib,sys
p=pathlib.Path(sys.argv[1])/'STATE.json'; d=json.loads(p.read_text())
try: extra=json.loads(sys.argv[5])
except Exception: extra={'raw':sys.argv[5]}
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); d['phase']=sys.argv[2]; d['updated_at']=now
d.setdefault('stages',{})[sys.argv[3]]={'status':sys.argv[4],'updated_at':now,**extra}
t=p.with_suffix('.tmp'); t.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n'); os.replace(t,p)
PY
}

require_stage(){
  local ws="$1" stage="$2" got
  got="$(state_get "$ws/STATE.json" "stages.$stage.status" 2>/dev/null || true)"
  [[ "$got" == PASS ]] || die "Required stage '$stage' is not PASS (observed: ${got:-missing})"
}

artifact_json(){
  python - "$@" <<'PY'
import hashlib,json,pathlib,sys
items=[]
for value in sys.argv[1:]:
    p=pathlib.Path(value).resolve(); items.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
print(json.dumps({'artifacts':items},sort_keys=True))
PY
}

verify_workspace(){
  python - "$1" <<'PY'
import hashlib,json,pathlib,sys
ws=pathlib.Path(sys.argv[1]); state=json.loads((ws/'STATE.json').read_text()); errors=[]
ledger=ws/'audit'/'events.jsonl'; prev='0'*64; seq=1
if not ledger.exists(): errors.append('audit ledger missing')
else:
    for line in ledger.read_text().splitlines():
        if not line.strip(): continue
        row=json.loads(line); event_hash=row.pop('event_hash',None)
        if row.get('seq')!=seq: errors.append(f'audit seq mismatch {seq}')
        if row.get('prev_hash')!=prev: errors.append(f'audit prev_hash mismatch {seq}')
        calc=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if calc!=event_hash: errors.append(f'audit event_hash mismatch {seq}')
        prev=event_hash or ''; seq+=1
for stage,rec in state.get('stages',{}).items():
    for item in rec.get('artifacts',[]) or []:
        p=pathlib.Path(item.get('path','')); expected=item.get('sha256')
        if not p.is_file(): errors.append(f'{stage}: missing {p}'); continue
        if expected and hashlib.sha256(p.read_bytes()).hexdigest()!=expected: errors.append(f'{stage}: hash mismatch {p}')
if errors:
    print('\n'.join(errors)); raise SystemExit(1)
print(f'PASS audit_events={seq-1}')
PY
}

init_workspace(){
  local ws="$1" schema10="$2" ga="$3"
  [[ ! -e "$ws/STATE.json" ]] || die "Workspace already initialized: $ws"
  mkdir -p "$ws"/{analysis,candidate,evidence,reports,audit,inputs,certification}
  python - "$ws" "$schema10" "$ga" "$VERSION" <<'PY'
import datetime,json,pathlib,sys
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); ws=pathlib.Path(sys.argv[1])
d={'format':'automation-rc4-controller-successor-state-v1','provenance_class':'RECONSTRUCTED_SUCCESSOR','controller_version':sys.argv[4],'target_release':'1.0.0-rc4-converged','minimum_schema_version':10,'phase':'INIT','promotion':'BLOCK','created_at':now,'updated_at':now,'inputs':{'schema10_installer':sys.argv[2] or None,'ga_installer':sys.argv[3] or None},'stages':{'init':{'status':'PASS','updated_at':now,'artifacts':[]}},'rules':['exact pinned parent identities','no schema downgrade','no last-writer-wins core merge','no host-for-physical substitution','verified device attestations required','native candidate certification required','no automatic GA promotion']}
(ws/'STATE.json').write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
PY
  append_event "$ws" init PASS "$(python -c 'import json,sys; print(json.dumps({"workspace":sys.argv[1],"provenance_class":"RECONSTRUCTED_SUCCESSOR"}))' "$ws")"
}

MODE="${1:-help}"; shift || true
[[ "$MODE" != help && "$MODE" != --help && "$MODE" != -h ]] || { usage; exit 0; }
need python; need sha256sum

case "$MODE" in
  init)
    [[ $# -ge 1 ]] || die 'init requires WORKSPACE'; WS="$(abs "$1")"; shift; S10=""; GA=""
    while [[ $# -gt 0 ]]; do case "$1" in --schema10) S10="$(abs "${2:?}")"; shift 2;; --ga) GA="$(abs "${2:?}")"; shift 2;; *) die "Unknown option: $1";; esac; done
    init_workspace "$WS" "$S10" "$GA"; log PASS "Initialized $WS"
    ;;
  status)
    [[ $# -eq 1 ]] || die 'status requires WORKSPACE'; WS="$(abs "$1")"; cat "$WS/STATE.json"
    ;;
  verify)
    [[ $# -eq 1 ]] || die 'verify requires WORKSPACE'; WS="$(abs "$1")"; verify_workspace "$WS"
    ;;
  analyze)
    [[ $# -ge 1 ]] || die 'analyze requires WORKSPACE'; WS="$(abs "$1")"; shift; [[ -f "$WS/STATE.json" ]] || die 'workspace not initialized'
    S10="$(state_get "$WS/STATE.json" inputs.schema10_installer 2>/dev/null || true)"; GA="$(state_get "$WS/STATE.json" inputs.ga_installer 2>/dev/null || true)"
    while [[ $# -gt 0 ]]; do case "$1" in --schema10) S10="$(abs "${2:?}")"; shift 2;; --ga) GA="$(abs "${2:?}")"; shift 2;; *) die "Unknown option: $1";; esac; done
    [[ -n "$S10" && -n "$GA" ]] || die 'both exact parent installers are required'
    OUT="$WS/analysis/current"; rm -rf "$OUT"
    if python "$ANALYZER" analyze --output "$OUT" --schema10 "$S10" --ga "$GA"; then
      R="$OUT/reports/RC4_BRANCH_DELTA.json"; Q="$OUT/reports/RC4_REVIEW_QUEUE.json"; DATA="$(artifact_json "$R" "$Q")"
      update_state "$WS" ANALYZED analyze PASS "$DATA"; append_event "$WS" analyze PASS "$DATA"; log PASS 'Exact-parent convergence analysis complete.'
    else
      update_state "$WS" INIT analyze FAIL '{}'; append_event "$WS" analyze FAIL '{}'; exit 1
    fi
    ;;
  construct)
    [[ $# -ge 3 ]] || die 'construct requires WORKSPACE --decisions FILE'; WS="$(abs "$1")"; shift; DEC=""
    while [[ $# -gt 0 ]]; do case "$1" in --decisions) DEC="$(abs "${2:?}")"; shift 2;; *) die "Unknown option: $1";; esac; done
    require_stage "$WS" analyze; [[ -f "$DEC" ]] || die "decisions missing: $DEC"
    OUT="$WS/candidate/current"; rm -rf "$OUT"
    if python "$CONSTRUCTOR" build --analysis "$WS/analysis/current" --decisions "$DEC" --output "$OUT"; then
      M="$OUT/reports/RC4_CONSTRUCTION_MANIFEST.json"; DATA="$(artifact_json "$M" "$DEC")"
      DATA="$(python - "$DATA" "$OUT/tree" <<'PY'
import json,pathlib,sys
x=json.loads(sys.argv[1]); x['candidate_tree']=str(pathlib.Path(sys.argv[2]).resolve()); print(json.dumps(x))
PY
)"
      update_state "$WS" CONSTRUCTED construct PASS "$DATA"; append_event "$WS" construct PASS "$DATA"; log PASS 'Candidate constructed; still non-installable and unqualified.'
    else
      update_state "$WS" ANALYZED construct FAIL '{}'; append_event "$WS" construct FAIL '{}'; exit 1
    fi
    ;;
  qualify-host)
    [[ $# -eq 1 ]] || die 'qualify-host requires WORKSPACE'; WS="$(abs "$1")"; require_stage "$WS" construct
    TREE="$(state_get "$WS/STATE.json" stages.construct.candidate_tree)"; OUT="$WS/reports/RC4_HOST_QUALIFICATION.json"
    if python "$HOST_HARNESS" "$TREE" "$OUT"; then
      DATA="$(artifact_json "$OUT")"; update_state "$WS" HOST_QUALIFIED qualify_host PASS "$DATA"; append_event "$WS" qualify_host PASS "$DATA"; log PASS 'Static host qualification PASS; physical gates remain open.'
    else
      DATA="$(artifact_json "$OUT" 2>/dev/null || printf '{}')"; update_state "$WS" CONSTRUCTED qualify_host FAIL "$DATA"; append_event "$WS" qualify_host FAIL "$DATA"; exit 1
    fi
    ;;
  gate-evidence)
    [[ $# -ge 3 ]] || die 'gate-evidence requires WORKSPACE --evidence DIR'; WS="$(abs "$1")"; shift; EVID=""
    while [[ $# -gt 0 ]]; do case "$1" in --evidence) EVID="$(abs "${2:?}")"; shift 2;; *) die "Unknown option: $1";; esac; done
    require_stage "$WS" qualify_host; [[ -d "$EVID" ]] || die "evidence directory missing: $EVID"; verify_workspace "$WS" >/dev/null
    TREE="$(state_get "$WS/STATE.json" stages.construct.candidate_tree)"
    if python "$EVIDENCE_GATE" "$TREE" "$EVID"; then
      G="$EVID/RC4_PROMOTION_EVIDENCE_GATE.json"; DATA="$(artifact_json "$G")"; update_state "$WS" EVIDENCE_GATED evidence_gate PASS "$DATA"; append_event "$WS" evidence_gate PASS "$DATA"; log PASS 'Physical evidence outer gate PASS. This is not certification or promotion.'
    else
      G="$EVID/RC4_PROMOTION_EVIDENCE_GATE.json"; DATA="$(artifact_json "$G" 2>/dev/null || printf '{}')"; update_state "$WS" HOST_QUALIFIED evidence_gate FAIL "$DATA"; append_event "$WS" evidence_gate FAIL "$DATA"; exit 1
    fi
    ;;
  certify)
    [[ $# -ge 3 ]] || die 'certify requires WORKSPACE --report FILE'; WS="$(abs "$1")"; shift; REPORT=""
    while [[ $# -gt 0 ]]; do case "$1" in --report) REPORT="$(abs "${2:?}")"; shift 2;; *) die "Unknown option: $1";; esac; done
    require_stage "$WS" evidence_gate; [[ -f "$REPORT" ]] || die "certification report missing: $REPORT"; verify_workspace "$WS" >/dev/null
    TREE="$(state_get "$WS/STATE.json" stages.construct.candidate_tree)"; HOST="$WS/reports/RC4_HOST_QUALIFICATION.json"; GATE_PATH="$(state_get "$WS/STATE.json" stages.evidence_gate.artifacts | python -c 'import json,sys; x=json.load(sys.stdin); print(x[0]["path"])')"
    python - "$SCRIPT_DIR" "$TREE" "$HOST" "$GATE_PATH" "$REPORT" <<'PY'
import hashlib,json,pathlib,sys
sys.path.insert(0,sys.argv[1]); from rc4_successor_common import candidate_digest
root=pathlib.Path(sys.argv[2]); host=pathlib.Path(sys.argv[3]); gate=pathlib.Path(sys.argv[4]); report=pathlib.Path(sys.argv[5]); d=json.loads(report.read_text())
errs=[]
if d.get('format')!='automation-rc4-candidate-certification-report-v1': errs.append('unexpected certification format')
if d.get('status')!='PASS' or d.get('native_engine_verified') is not True: errs.append('native certification is not verified PASS')
if d.get('release')!='1.0.0-rc4-converged' or int(d.get('schema_version',-1))!=10: errs.append('release/schema mismatch')
if d.get('candidate_tree_root_sha256')!=candidate_digest(root): errs.append('candidate digest mismatch')
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
if d.get('host_qualification_sha256')!=sha(host): errs.append('host qualification binding mismatch')
if d.get('promotion_evidence_gate_sha256')!=sha(gate): errs.append('evidence gate binding mismatch')
for name in ['certificate_chain','audit_chain','sqlite_integrity','foreign_keys','recovery_drill','rollback_paths']:
    if (d.get('checks') or {}).get(name) != 'PASS': errs.append(f'certification check not PASS: {name}')
for name in ['fresh->rc4','rc2-schema10->rc4','rc3-device-validation-schema10->rc4','rc3-ga-campaign-schema9->rc4']:
    if (d.get('migration_paths') or {}).get(name) != 'PASS': errs.append(f'migration path not PASS: {name}')
if errs: raise SystemExit('\n'.join(errs))
print('PASS native candidate certification verified')
PY
    DEST="$WS/certification/RC4_CANDIDATE_CERTIFICATION_REPORT.json"; cp "$REPORT" "$DEST"; DATA="$(artifact_json "$DEST")"; update_state "$WS" CERTIFIED certification PASS "$DATA"; append_event "$WS" certification PASS "$DATA"; log PASS 'Native candidate certification verified. Promotion is still blocked.'
    ;;
  readiness)
    [[ $# -ge 3 ]] || die 'readiness requires WORKSPACE --reviewed-by NAME'; WS="$(abs "$1")"; shift; REVIEWER=""
    while [[ $# -gt 0 ]]; do case "$1" in --reviewed-by) REVIEWER="${2:?}"; shift 2;; *) die "Unknown option: $1";; esac; done
    require_stage "$WS" certification; [[ -n "${REVIEWER// }" ]] || die 'reviewed-by may not be blank'; verify_workspace "$WS" >/dev/null
    OUT="$WS/reports/RC4_PROMOTION_READINESS.json"
    python - "$OUT" "$REVIEWER" <<'PY'
import datetime,json,pathlib,sys
x={'format':'automation-rc4-promotion-readiness-successor-v1','provenance_class':'RECONSTRUCTED_SUCCESSOR','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'READY_FOR_EXPLICIT_HUMAN_PROMOTION_DECISION','reviewed_by':sys.argv[2],'automatic_promotion_performed':False,'promotion_performed':False,'notes':['This is readiness evidence only. No Git tag, release, installer execution, merge, or promotion was performed.']}
pathlib.Path(sys.argv[1]).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
PY
    DATA="$(artifact_json "$OUT")"; update_state "$WS" READY_FOR_HUMAN_PROMOTION readiness PASS "$DATA"
    python - "$WS/STATE.json" <<'PY'
import json,os,pathlib,sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text()); d['promotion']='BLOCK_PENDING_EXPLICIT_HUMAN_ACTION'; t=p.with_suffix('.tmp'); t.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n'); os.replace(t,p)
PY
    append_event "$WS" readiness PASS "$DATA"; log PASS 'Ready for explicit human decision; no promotion performed.'
    ;;
  *) usage; exit 2;;
esac
