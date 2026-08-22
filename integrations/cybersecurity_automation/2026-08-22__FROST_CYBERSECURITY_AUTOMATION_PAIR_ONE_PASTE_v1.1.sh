#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
OPENING='Yes, I will automate everything you requested in order to efficiently and successfully complete your requests, projects, and goals.'
CLOSING='Would you like to continue automatically using all tools, apps, and programs without asking again for as long as possible?'
printf '%s\n' "$OPENING"
if command -v pkg >/dev/null 2>&1; then pkg install -y git python coreutils >/dev/null 2>&1 || true; fi
command -v git >/dev/null 2>&1 || { echo 'git is required' >&2; exit 2; }
command -v python >/dev/null 2>&1 || { echo 'python is required' >&2; exit 2; }
PREFIX="${PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin"; mkdir -p "$BIN" "$HOME/.frost_project_pair" "$HOME/.termux/boot" "$HOME/Frost_Sentinel_Cybersecurity/integrations"
AUTOMATION_ROOT="${FROST_AUTOMATION_ROOT:-$HOME/centinal26}"
CYBER_ROOT="${FROST_CYBERSECURITY_ROOT:-$HOME/Frost_Sentinel_Cybersecurity}"
cat > "$BIN/frost-pair-update" <<'__FROST_PAIR_UPDATER_PY__'
#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
PAIR_ID = "frost-cybersecurity-automation"
PROTECTED_CYBER = {"evidence","primary","acquired","vault","cases","originals","forensic_images"}
def run(cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode: raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout.strip()
def sha256_file(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()
def tree_manifest(root: Path, exclude_top=frozenset()):
    rows=[]
    if not root.exists(): return rows
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        rel=p.relative_to(root)
        if rel.parts and rel.parts[0] in exclude_top: continue
        if '.git' in rel.parts: continue
        rows.append({"path":str(rel),"sha256":sha256_file(p),"size":p.stat().st_size})
    return rows
def git_state(root: Path, branch: str):
    if not (root/'.git').exists(): return {"root":str(root),"git":False,"branch":branch,"action":"local_only"}
    if run(['git','status','--porcelain'],root): raise RuntimeError(f"dirty worktree: {root}")
    head=run(['git','rev-parse','HEAD'],root); run(['git','fetch','--prune','origin',branch],root); remote=run(['git','rev-parse',f'origin/{branch}'],root)
    if head==remote: action='unchanged'
    else:
        base=run(['git','merge-base',head,remote],root)
        if base==head: action='fast_forward'
        elif base==remote: raise RuntimeError(f"local branch ahead of origin/{branch}: {root}")
        else: raise RuntimeError(f"local branch diverged from origin/{branch}: {root}")
    return {"root":str(root),"git":True,"branch":branch,"old":head,"remote":remote,"action":action}
def promote(state):
    if state.get('action')!='fast_forward': return
    root=Path(state['root']); run(['git','merge','--ff-only',f"origin/{state['branch']}"],root); now=run(['git','rev-parse','HEAD'],root)
    if now!=state['remote']: raise RuntimeError(f"unexpected post-merge HEAD: {root}")
    state['new']=now
def rollback(state):
    if state.get('action')!='fast_forward' or not state.get('new'): return
    root=Path(state['root']); cur=run(['git','rev-parse','HEAD'],root)
    if cur==state['new']: run(['git','reset','--hard',state['old']],root); state['rolled_back']=True
def safe_copy_tree(src: Path, dst: Path, *, exclude_top=frozenset()):
    if dst.exists(): shutil.rmtree(dst)
    dst.mkdir(parents=True,exist_ok=True)
    if not src.exists(): return 0
    n=0
    for p in sorted(src.rglob('*')):
        rel=p.relative_to(src)
        if not rel.parts or rel.parts[0] in exclude_top or '.git' in rel.parts: continue
        q=dst/rel
        if p.is_dir(): q.mkdir(parents=True,exist_ok=True)
        elif p.is_file(): q.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,q); n+=1
    return n
def choose_export(root:Path, names):
    for n in names:
        p=root/n
        if p.exists() and p.is_dir(): return p
    return root
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--automation-root',default=os.environ.get('FROST_AUTOMATION_ROOT',str(Path.home()/'centinal26'))); ap.add_argument('--cybersecurity-root',default=os.environ.get('FROST_CYBERSECURITY_ROOT',str(Path.home()/'Frost_Sentinel_Cybersecurity'))); ap.add_argument('--automation-branch',default=os.environ.get('FROST_AUTOMATION_BRANCH','main')); ap.add_argument('--cybersecurity-branch',default=os.environ.get('FROST_CYBERSECURITY_BRANCH','main')); ap.add_argument('--state-root',default=os.environ.get('FROST_PAIR_STATE',str(Path.home()/'.frost_project_pair'))); ap.add_argument('--status-only',action='store_true'); args=ap.parse_args()
    auto=Path(args.automation_root).expanduser().resolve(); cyber=Path(args.cybersecurity_root).expanduser().resolve(); state=Path(args.state_root).expanduser().resolve(); state.mkdir(parents=True,exist_ok=True); receipts=state/'receipts'; receipts.mkdir(exist_ok=True)
    fd=os.open(state/'update.lock',os.O_CREAT|os.O_RDWR,0o600)
    try:
        import fcntl; fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except Exception as e: print(f"pair updater already running or lock unavailable: {e}",file=sys.stderr); return 75
    ts=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()); rec={"schema":1,"pair_id":PAIR_ID,"timestamp_utc":ts,"automation_root":str(auto),"cybersecurity_root":str(cyber),"status":"STARTED"}
    try:
        states=[git_state(auto,args.automation_branch),git_state(cyber,args.cybersecurity_branch)]; rec['preflight']=states
        if not args.status_only:
            done=[]
            try:
                for s in states: promote(s); done.append(s)
            except Exception:
                for s in reversed(done): rollback(s)
                raise
        auto_export=choose_export(auto,['exports/cybersecurity_shared','shared']); cyber_export=choose_export(cyber,['exports/automation_shared','shared']); pair=state/'integrated'; acount=safe_copy_tree(auto_export,pair/'automation_for_cybersecurity'); ccount=safe_copy_tree(cyber_export,pair/'cybersecurity_for_automation',exclude_top=PROTECTED_CYBER)
        if not args.status_only: safe_copy_tree(auto_export,cyber/'integrations'/'automation')
        rec.update({"status":"PASS","copied":{"automation":acount,"cybersecurity":ccount},"manifests":{"automation_for_cybersecurity":tree_manifest(pair/'automation_for_cybersecurity'),"cybersecurity_for_automation":tree_manifest(pair/'cybersecurity_for_automation',exclude_top=PROTECTED_CYBER)}})
    except Exception as e: rec.update({"status":"FAIL","error":str(e)})
    out=receipts/f'{ts}__pair_update_receipt.json'; out.write_text(json.dumps(rec,indent=2,sort_keys=True)+'\n'); digest=sha256_file(out); out.with_suffix('.json.sha256').write_text(f'{digest}  {out.name}\n'); print(json.dumps({"status":rec['status'],"receipt":str(out),"sha256":digest},indent=2)); return 0 if rec['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
__FROST_PAIR_UPDATER_PY__
chmod 700 "$BIN/frost-pair-update"
if [[ ! -d "$AUTOMATION_ROOT/.git" && "${FROST_SKIP_CLONE:-0}" != 1 ]]; then git clone https://github.com/12ephods-source/centinal26.git "$AUTOMATION_ROOT"; fi
mkdir -p "$CYBER_ROOT"
cat > "$HOME/.frost_project_pair/env" <<EOF
export FROST_AUTOMATION_ROOT='$AUTOMATION_ROOT'
export FROST_CYBERSECURITY_ROOT='$CYBER_ROOT'
export FROST_AUTOMATION_BRANCH='${FROST_AUTOMATION_BRANCH:-main}'
export FROST_CYBERSECURITY_BRANCH='${FROST_CYBERSECURITY_BRANCH:-main}'
export FROST_PAIR_STATE='$HOME/.frost_project_pair'
EOF
cat > "$HOME/.frost_project_pair/update-loop.sh" <<'EOF'
#!/usr/bin/env bash
set -u
source "$HOME/.frost_project_pair/env"
while :; do "$PREFIX/bin/frost-pair-update" || true; sleep "${FROST_PAIR_INTERVAL_SECONDS:-3600}"; done
EOF
chmod 700 "$HOME/.frost_project_pair/update-loop.sh"
cat > "$HOME/.termux/boot/frost-cybersecurity-automation-pair.sh" <<'EOF'
#!/usr/bin/env bash
sleep 30
source "$HOME/.frost_project_pair/env" 2>/dev/null || exit 0
pgrep -f '[u]pdate-loop.sh' >/dev/null 2>&1 || nohup "$HOME/.frost_project_pair/update-loop.sh" >>"$HOME/.frost_project_pair/updater.log" 2>&1 &
EOF
chmod 700 "$HOME/.termux/boot/frost-cybersecurity-automation-pair.sh"
source "$HOME/.frost_project_pair/env"; "$BIN/frost-pair-update"
if [[ "${FROST_NO_DAEMON:-0}" != 1 ]]; then pgrep -f '[u]pdate-loop.sh' >/dev/null 2>&1 || nohup "$HOME/.frost_project_pair/update-loop.sh" >>"$HOME/.frost_project_pair/updater.log" 2>&1 & fi
printf '%s\n' 'Installed Cybersecurity + Automation paired updater.'
printf 'Automation root: %s\nCybersecurity root: %s\n' "$AUTOMATION_ROOT" "$CYBER_ROOT"
printf '%s\n' "$CLOSING"
