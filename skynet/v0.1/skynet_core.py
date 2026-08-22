#!/usr/bin/env python3
import argparse, hashlib, hmac, json, os, sqlite3, subprocess, sys, time, uuid
from pathlib import Path

APP_HOME = Path(os.environ.get('SKYNET_HOME', str(Path.home()/'.skynet')))
DB = APP_HOME/'state.db'
KEY = APP_HOME/'secret.key'
CFG = APP_HOME/'config.json'
AUDIT = APP_HOME/'audit.jsonl'

DEFAULT_CFG = {
  'version':'0.1.0',
  'node_id':None,
  'allowed_tasks':['health','project_update','snapshot','verify'],
  'project_paths':{
    'automation': str(Path.home()/'centinal26'),
    'cybersecurity': str(Path.home()/'frost-sentinel')
  },
  'protected_paths':['evidence','primary','acquired','vault','cases','originals','forensic_images'],
  'max_runtime_seconds':300
}

def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def sha256b(b): return hashlib.sha256(b).hexdigest()
def read_key(): return KEY.read_bytes()
def canon(obj): return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
def sign(obj): return hmac.new(read_key(), canon(obj), hashlib.sha256).hexdigest()
def verify_sig(obj,sig): return hmac.compare_digest(sign(obj),sig)

def audit(kind, data):
    APP_HOME.mkdir(parents=True,exist_ok=True)
    prev='0'*64
    if AUDIT.exists():
        try: prev=json.loads(AUDIT.read_text().splitlines()[-1])['hash']
        except Exception: pass
    rec={'ts':now(),'kind':kind,'data':data,'prev':prev}
    rec['hash']=sha256b(canon(rec))
    with AUDIT.open('a') as f: f.write(json.dumps(rec,sort_keys=True)+'\n')
    return rec

def db():
    c=sqlite3.connect(DB)
    c.execute('create table if not exists jobs(id text primary key, type text, payload text, state text, created text, updated text, result text)')
    c.execute('create table if not exists nodes(node_id text primary key, last_seen text, meta text)')
    c.commit(); return c

def init():
    APP_HOME.mkdir(parents=True,exist_ok=True)
    if not KEY.exists(): KEY.write_bytes(os.urandom(32)); os.chmod(KEY,0o600)
    if not CFG.exists():
        cfg=dict(DEFAULT_CFG); cfg['node_id']=str(uuid.uuid4()); CFG.write_text(json.dumps(cfg,indent=2)+'\n')
    db().close(); audit('init',{'home':str(APP_HOME)})
    print(str(APP_HOME))

def cfg(): return json.loads(CFG.read_text())

def _run(cmd, cwd):
    return subprocess.run(cmd,cwd=cwd,text=True,capture_output=True)

def git_state(path):
    p=Path(path)
    if not (p/'.git').exists(): return {'ok':False,'reason':'not_git_repo','path':str(p)}
    dirty=_run(['git','status','--porcelain'],p).stdout.strip()
    if dirty: return {'ok':False,'reason':'dirty_worktree','path':str(p)}
    branch=_run(['git','rev-parse','--abbrev-ref','HEAD'],p).stdout.strip()
    fr=_run(['git','fetch','--prune','origin',branch],p)
    if fr.returncode: return {'ok':False,'reason':'fetch_failed','stderr':fr.stderr[-1000:]}
    head=_run(['git','rev-parse','HEAD'],p).stdout.strip(); remote=_run(['git','rev-parse',f'origin/{branch}'],p).stdout.strip()
    if head==remote: return {'ok':True,'action':'unchanged','path':str(p),'branch':branch,'old':head,'remote':remote}
    mb=_run(['git','merge-base',head,remote],p)
    if mb.returncode: return {'ok':False,'reason':'merge_base_failed'}
    base=mb.stdout.strip()
    if base==head: return {'ok':True,'action':'fast_forward','path':str(p),'branch':branch,'old':head,'remote':remote}
    if base==remote: return {'ok':False,'reason':'local_ahead','path':str(p)}
    return {'ok':False,'reason':'diverged','path':str(p)}

def promote(state):
    if state.get('action')!='fast_forward': return True
    p=Path(state['path']); r=_run(['git','merge','--ff-only',f"origin/{state['branch']}"],p)
    if r.returncode: return False
    state['new']=_run(['git','rev-parse','HEAD'],p).stdout.strip()
    return state['new']==state['remote']

def rollback(state):
    if state.get('action')!='fast_forward' or not state.get('new'): return
    p=Path(state['path']); cur=_run(['git','rev-parse','HEAD'],p).stdout.strip()
    if cur==state['new']:
        _run(['git','reset','--hard',state['old']],p); state['rolled_back']=True

def paired_project_update(project_paths):
    states={k:git_state(v) for k,v in project_paths.items()}
    if not all(x.get('ok') for x in states.values()): return {'ok':False,'phase':'preflight','projects':states}
    done=[]
    try:
        for name,state in states.items():
            if not promote(state): raise RuntimeError(f'promotion_failed:{name}')
            done.append(state)
    except Exception as e:
        for state in reversed(done): rollback(state)
        return {'ok':False,'phase':'promotion','error':str(e),'projects':states}
    return {'ok':True,'phase':'complete','projects':states}

def run_task(t,payload):
    c=cfg()
    if t not in c['allowed_tasks']: return {'ok':False,'error':'task_not_allowed'}
    if t=='health': return {'ok':True,'node_id':c['node_id'],'ts':now()}
    if t=='verify':
        checks={}
        for k,v in c['project_paths'].items(): checks[k]={'exists':Path(v).exists(),'git':(Path(v)/'.git').exists()}
        return {'ok':all(x['exists'] for x in checks.values()),'checks':checks}
    if t=='project_update':
        return paired_project_update(c['project_paths'])
    if t=='snapshot':
        out=APP_HOME/'snapshots'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()); out.mkdir(parents=True,exist_ok=True)
        manifests={}
        for name,path in c['project_paths'].items():
            p=Path(path); rows=[]
            if p.exists():
                for f in p.rglob('*'):
                    if f.is_file() and '.git' not in f.parts and not any(x in f.parts for x in c['protected_paths']):
                        try: rows.append((str(f.relative_to(p)),sha256b(f.read_bytes())))
                        except Exception: pass
            mf=out/f'{name}.sha256.json'; mf.write_text(json.dumps(rows,indent=2)+'\n'); manifests[name]=str(mf)
        return {'ok':True,'snapshot':str(out),'manifests':manifests}
    return {'ok':False,'error':'unimplemented'}

def submit(t,payload):
    c=cfg(); job={'id':str(uuid.uuid4()),'type':t,'payload':payload,'created':now(),'node_id':c['node_id']}; sig=sign(job)
    d=db(); d.execute('insert into jobs values(?,?,?,?,?,?,?)',(job['id'],t,json.dumps(payload),'queued',job['created'],job['created'],None)); d.commit(); d.close()
    audit('job_submit',{'job':job,'sig':sig}); print(json.dumps({'job':job,'sig':sig},indent=2))

def work_once():
    d=db(); row=d.execute("select id,type,payload from jobs where state='queued' order by created limit 1").fetchone()
    if not row: print(json.dumps({'ok':True,'idle':True})); return
    jid,t,p=row; d.execute("update jobs set state='running',updated=? where id=?",(now(),jid)); d.commit()
    try: result=run_task(t,json.loads(p)); state='done' if result.get('ok') else 'failed'
    except Exception as e: result={'ok':False,'error':type(e).__name__,'detail':str(e)}; state='failed'
    d.execute('update jobs set state=?,updated=?,result=? where id=?',(state,now(),json.dumps(result),jid)); d.commit(); d.close(); audit('job_result',{'id':jid,'state':state,'result':result}); print(json.dumps({'id':jid,'state':state,'result':result},indent=2))

def status():
    d=db(); jobs=d.execute('select id,type,state,created,updated,result from jobs order by created desc limit 20').fetchall(); d.close()
    print(json.dumps({'config':cfg(),'jobs':[{'id':r[0],'type':r[1],'state':r[2],'created':r[3],'updated':r[4],'result':json.loads(r[5]) if r[5] else None} for r in jobs]},indent=2))

def verify_audit():
    prev='0'*64; ok=True; n=0
    if AUDIT.exists():
      for line in AUDIT.read_text().splitlines():
        rec=json.loads(line); h=rec.pop('hash'); ok &= rec.get('prev')==prev and sha256b(canon(rec))==h; prev=h; n+=1
    print(json.dumps({'ok':bool(ok),'records':n,'head':prev},indent=2)); sys.exit(0 if ok else 2)

def main():
    ap=argparse.ArgumentParser(prog='skynet'); sp=ap.add_subparsers(dest='cmd',required=True)
    sp.add_parser('init'); s=sp.add_parser('submit'); s.add_argument('type'); s.add_argument('--payload',default='{}'); sp.add_parser('work-once'); sp.add_parser('status'); sp.add_parser('verify-audit')
    a=ap.parse_args()
    if a.cmd=='init': init()
    elif a.cmd=='submit': submit(a.type,json.loads(a.payload))
    elif a.cmd=='work-once': work_once()
    elif a.cmd=='status': status()
    elif a.cmd=='verify-audit': verify_audit()
if __name__=='__main__': main()
