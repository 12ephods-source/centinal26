#!/usr/bin/env python3
from __future__ import annotations
import json, os, signal, subprocess, time
from pathlib import Path

ROOT=Path(os.environ.get("CENTINAL26_HOME",str(Path.home()/".centinal26")))
BIN=ROOT/"bin"; STATE=ROOT/"state"; LOGS=ROOT/"logs"
PID=STATE/"daemon.pid"; STOP=STATE/"GUARDIAN_STOP"
INTERVAL=max(1800,int(os.environ.get("CENTINAL26_RECONCILE_INTERVAL","1800")))

def alive():
    try:
        p=int(PID.read_text().strip()); os.kill(p,0); return True
    except Exception: return False

def start_daemon():
    subprocess.run([str(BIN/"centinal26_daemon_service.sh"),"start"],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def cycle():
    cp=subprocess.run(["python",str(BIN/"centinal26_improvement_cycle.py")],text=True,capture_output=True,timeout=120)
    rec={"ts":int(time.time()),"returncode":cp.returncode,"stdout":cp.stdout[-10000:],"stderr":cp.stderr[-10000:]}
    with (LOGS/"guardian.jsonl").open("a") as f: f.write(json.dumps(rec,sort_keys=True)+"\n")

def main():
    STATE.mkdir(parents=True,exist_ok=True); LOGS.mkdir(parents=True,exist_ok=True)
    STOP.unlink(missing_ok=True)
    next_cycle=0
    while not STOP.exists():
        if not alive(): start_daemon()
        now=time.time()
        if now>=next_cycle:
            cycle(); next_cycle=now+INTERVAL
        time.sleep(30)
    return 0
if __name__=="__main__": raise SystemExit(main())
