#!/usr/bin/env python3
import argparse, hashlib, json, os, pathlib, tempfile, time, uuid
from dataclasses import dataclass

SCHEMA=3
QUALIFIED=("repo_sync","repo_clean","pair_ok","skynet_ok","device_boot_ok","device_restart_ok","device_exec_ok","device_audit_ok","state_integrity_ok","recovery_ok")


def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
def sha(b): return hashlib.sha256(b).hexdigest()

def atomic_write(path: pathlib.Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        dfd=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

@dataclass
class Kernel:
    root:pathlib.Path
    def __post_init__(self):
        self.root.mkdir(parents=True,exist_ok=True)
        self.state=self.root/"project_state.json"
        self.ledger=self.root/"evidence.jsonl"
        self.marker=self.root/"PROJECT_GOAL_REACHED"

    def load(self):
        if not self.state.exists():
            return {"schema":SCHEMA,"release":None,"status":"UNQUALIFIED","generation":0,"checks":{k:False for k in QUALIFIED},"metrics":{"cycles":0,"recoveries":0,"demotions":0},"last_event_hash":None}
        obj=json.loads(self.state.read_text())
        if obj.get("schema")!=SCHEMA: raise RuntimeError("unsupported state schema")
        return obj

    def append_event(self,event):
        prev=None
        if self.ledger.exists():
            lines=self.ledger.read_text().splitlines()
            if lines: prev=json.loads(lines[-1])["event_hash"]
        body={"schema":SCHEMA,"event_id":str(uuid.uuid4()),"time_utc":now(),"prev_event_hash":prev,**event}
        body["event_hash"]=sha(json.dumps(body,sort_keys=True,separators=(",",":")).encode())
        with self.ledger.open("a") as f:
            f.write(json.dumps(body,sort_keys=True)+"\n"); f.flush(); os.fsync(f.fileno())
        return body["event_hash"]

    def commit(self,release,checks,detail="",worker="kernel",inputs=None):
        old=self.load(); normalized={k:bool(checks.get(k,False)) for k in QUALIFIED}
        goal=all(normalized.values())
        old_goal=old.get("status")=="PROJECT_GOAL_REACHED"
        metrics=dict(old.get("metrics",{})); metrics["cycles"]=int(metrics.get("cycles",0))+1
        if old_goal and not goal: metrics["demotions"]=int(metrics.get("demotions",0))+1
        if detail.startswith("recovered:"): metrics["recoveries"]=int(metrics.get("recoveries",0))+1
        status="PROJECT_GOAL_REACHED" if goal else ("DEMOTED" if old_goal else "UNQUALIFIED")
        event_hash=self.append_event({"type":"qualification","release":release,"worker":worker,"inputs":inputs or {},"checks":normalized,"status":status,"detail":detail})
        obj={"schema":SCHEMA,"release":release,"status":status,"goal_reached":goal,"generation":int(old.get("generation",0))+1,"updated_at_utc":now(),"checks":normalized,"metrics":metrics,"last_event_hash":event_hash}
        payload=(json.dumps(obj,indent=2,sort_keys=True)+"\n").encode(); atomic_write(self.state,payload)
        atomic_write(pathlib.Path(str(self.state)+".sha256"),(sha(payload)+"  "+self.state.name+"\n").encode())
        if goal: atomic_write(self.marker,(release+" "+obj["updated_at_utc"]+" "+event_hash+"\n").encode())
        elif self.marker.exists(): self.marker.unlink()
        return obj

    def verify(self):
        obj=self.load(); problems=[]
        if self.state.exists():
            side=pathlib.Path(str(self.state)+".sha256")
            if not side.exists() or side.read_text().split()[0]!=sha(self.state.read_bytes()): problems.append("state_hash")
        prev=None
        if self.ledger.exists():
            for n,line in enumerate(self.ledger.read_text().splitlines(),1):
                e=json.loads(line); eh=e.pop("event_hash")
                if e.get("prev_event_hash")!=prev: problems.append(f"ledger_chain:{n}")
                if sha(json.dumps(e,sort_keys=True,separators=(",",":")).encode())!=eh: problems.append(f"ledger_hash:{n}")
                prev=eh
        if obj.get("last_event_hash")!=prev and self.ledger.exists(): problems.append("state_ledger_head")
        if obj.get("goal_reached")!=all(obj.get("checks",{}).get(k,False) for k in QUALIFIED): problems.append("goal_logic")
        if obj.get("goal_reached")!=self.marker.exists(): problems.append("goal_marker")
        return problems


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--state",default=os.path.expanduser("~/.frost_persistent_v3")); sub=ap.add_subparsers(dest="cmd",required=True)
    c=sub.add_parser("commit"); c.add_argument("--release",required=True); c.add_argument("--checks-json",required=True); c.add_argument("--detail",default=""); c.add_argument("--worker",default="kernel"); c.add_argument("--inputs-json",default="{}")
    sub.add_parser("verify"); sub.add_parser("status")
    a=ap.parse_args(); k=Kernel(pathlib.Path(a.state))
    if a.cmd=="commit": print(json.dumps(k.commit(a.release,json.loads(a.checks_json),a.detail,a.worker,json.loads(a.inputs_json)),sort_keys=True))
    elif a.cmd=="verify":
        p=k.verify(); print(json.dumps({"ok":not p,"problems":p})); raise SystemExit(0 if not p else 1)
    else: print(json.dumps(k.load(),indent=2,sort_keys=True))
if __name__=="__main__": main()
