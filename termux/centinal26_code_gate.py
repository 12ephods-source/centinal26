#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(os.environ.get("CENTINAL26_HOME", str(Path.home()/".centinal26"))).expanduser()
INBOX = ROOT/"code_inbox"; EVID = ROOT/"evidence"/"code_gate"; REPORTS = ROOT/"reports"/"code_gate"
for p in (INBOX,EVID,REPORTS): p.mkdir(parents=True, exist_ok=True)

MAX_PASSES = 5

def sha(path: Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def run(argv:list[str], cwd:Path, timeout:int=180)->dict:
    t=time.time()
    cp=subprocess.run(argv,cwd=str(cwd),text=True,capture_output=True,timeout=timeout,check=False)
    return {"argv":argv,"returncode":cp.returncode,"stdout":cp.stdout[-12000:],"stderr":cp.stderr[-12000:],"duration_s":round(time.time()-t,3)}

def classify(path:Path)->str:
    if path.suffix==".py": return "python"
    if path.suffix in {".sh",".bash"}: return "shell"
    if path.suffix==".js": return "javascript"
    if path.suffix==".ts": return "typescript"
    return "unknown"

def safety_scan(path:Path)->dict:
    txt=path.read_text(errors="replace")
    patterns=["curl | sh","curl|sh","wget | sh","wget|sh","rm -rf /","mkfs.",":(){ :|:& };:"]
    hits=[p for p in patterns if p in txt]
    return {"status":"PASS" if not hits else "REVIEW","hits":hits}

def tests(path:Path, lang:str)->list[dict]:
    cwd=path.parent; out=[]
    if lang=="python":
        out.append(run([sys.executable,"-m","py_compile",str(path)],cwd))
        if shutil.which("ruff"): out.append(run(["ruff","check",str(path)],cwd))
        if (cwd/"tests").exists() and shutil.which("pytest"): out.append(run(["pytest","-q"],cwd,timeout=900))
    elif lang=="shell":
        out.append(run(["bash","-n",str(path)],cwd))
        if shutil.which("shellcheck"): out.append(run(["shellcheck",str(path)],cwd))
    elif lang=="javascript" and shutil.which("node"):
        out.append(run(["node","--check",str(path)],cwd))
    elif lang=="typescript" and shutil.which("tsc"):
        out.append(run(["tsc","--noEmit",str(path)],cwd,timeout=900))
    else:
        out.append({"argv":[],"returncode":2,"stdout":"","stderr":"unsupported language or missing validator","duration_s":0})
    return out

def deterministic_improve(path:Path, lang:str)->dict:
    before=sha(path); actions=[]
    if lang=="python" and shutil.which("ruff"):
        r=run(["ruff","check","--fix",str(path)],path.parent); actions.append(r)
        if shutil.which("black"): actions.append(run(["black","-q",str(path)],path.parent))
    elif lang=="shell" and shutil.which("shfmt"):
        actions.append(run(["shfmt","-w",str(path)],path.parent))
    return {"changed":sha(path)!=before,"actions":actions,"before_sha256":before,"after_sha256":sha(path)}

def execute(path:Path, lang:str, args:list[str], timeout:int)->dict:
    if lang=="python": argv=[sys.executable,str(path),*args]
    elif lang=="shell": argv=["bash",str(path),*args]
    elif lang=="javascript": argv=["node",str(path),*args]
    else: raise SystemExit("execution unsupported for language")
    return run(argv,path.parent,min(timeout,900))

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("path"); ap.add_argument("--arg",action="append",default=[]); ap.add_argument("--timeout",type=int,default=180); ap.add_argument("--no-run",action="store_true")
    ns=ap.parse_args(); src=Path(ns.path).expanduser().resolve()
    if not src.is_file(): raise SystemExit("file not found")
    lang=classify(src); task=f"cg-{int(time.time())}-{sha(src)[:12]}"; work=INBOX/task; work.mkdir(parents=True)
    dst=work/src.name; shutil.copy2(src,dst)
    report={"task_id":task,"owner_class":"USER_EVIDENCE","origin_class":"ANDROID_TERMUX_DEVICE","source_path":str(src),"source_sha256":sha(src),"language":lang,"safety":safety_scan(dst),"passes":[]}
    if report["safety"]["status"]!="PASS": report["state"]="REVIEW"; REPORTS.joinpath(task+".json").write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2)); return 3
    plateau=0; previous=None
    for i in range(MAX_PASSES):
        tr=tests(dst,lang); ok=all(x["returncode"]==0 for x in tr); imp={"changed":False,"actions":[]}
        if not ok: imp=deterministic_improve(dst,lang)
        score=sum(1 for x in tr if x["returncode"]==0)
        sig=(score,sha(dst))
        plateau=plateau+1 if sig==previous else 0; previous=sig
        report["passes"].append({"pass":i+1,"tests":tr,"improvement":imp,"score":score,"sha256":sha(dst)})
        if ok or plateau>=1: break
    final_tests=tests(dst,lang); qualified=all(x["returncode"]==0 for x in final_tests)
    report["final_tests"]=final_tests; report["qualified"]=qualified; report["qualified_sha256"]=sha(dst)
    if qualified and not ns.no_run:
        report["execution"]=execute(dst,lang,ns.arg,ns.timeout); report["verification"]={"status":"PASS" if report["execution"]["returncode"]==0 else "FAIL","basis":"process_returncode_plus_preexecution_qualification"}
    else:
        report["execution"]={"skipped":True}; report["verification"]={"status":"PASS" if qualified else "FAIL","basis":"qualification_only"}
    report["state"]="COMPLETE" if report["verification"]["status"]=="PASS" else "FAILED"
    out=REPORTS/(task+".json"); out.write_text(json.dumps(report,indent=2)); os.chmod(out,0o600)
    evidence=EVID/(task+".sha256"); evidence.write_text(f"{sha(out)}  {out.name}\n"); os.chmod(evidence,0o600)
    print(json.dumps(report,indent=2)); return 0 if report["verification"]["status"]=="PASS" else 1

if __name__=="__main__": raise SystemExit(main())
