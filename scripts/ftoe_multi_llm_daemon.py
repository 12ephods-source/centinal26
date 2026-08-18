#!/usr/bin/env python3
"""FToE autonomous research daemon.

Scientific failures kill a branch, not the daemon. Missing external LLM credentials
remove that provider from the panel, not the research loop. Only an explicit STOP
file or process signal stops the daemon. Model responses are advisory: they never
execute shell commands or self-authorize repository mutations.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, os, pathlib, signal, subprocess, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = pathlib.Path(os.environ.get("FTOE_AUTOPILOT_STATE", pathlib.Path.home()/".local/state/ftoe-autopilot"))
STOP = STATE / "STOP"
AUDIT = STATE / "audit.jsonl"
CONFIG = ROOT / "physics/ftoe/agent_panel_config.json"
RUNNING = True

ALLOWLIST = [
 [sys.executable,"scripts/ftoe_so10_group_theory_gate.py"],
 [sys.executable,"-m","unittest","tests.test_ftoe_so10_group_theory_gate","-v"],
 [sys.executable,"-m","unittest","tests.test_ftoe_so10_422_gate","-v"],
 [sys.executable,"-m","unittest","tests.test_ftoe_so10_uv_closure","-v"],
 [sys.executable,"-m","unittest","tests.test_ftoe_so10_threshold_stress","-v"],
]

def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()
def emit(kind,data):
 STATE.mkdir(parents=True,exist_ok=True)
 row={"ts":utc(),"kind":kind,"data":data}
 row["sha256"]=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()
 with AUDIT.open("a") as f: f.write(json.dumps(row,sort_keys=True)+"\n")

def http_json(url, method="GET", payload=None, token=None, timeout=180):
 body=None if payload is None else json.dumps(payload).encode()
 headers={"Content-Type":"application/json"}
 if token: headers["Authorization"]="Bearer "+token
 req=urllib.request.Request(url,data=body,headers=headers,method=method)
 with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def discover(cfg):
 key=os.environ.get("AI_GATEWAY_API_KEY")
 if not key: return []
 data=http_json(cfg["gateway_base_url"]+"/models",token=key).get("data",[])
 now=int(time.time()); selected=[]
 for provider in cfg["providers"]:
  c=[m for m in data if m.get("id","").startswith(provider+"/") and m.get("type","language")=="language" and (not m.get("released") or m["released"]<=now)]
  def score(m):
   tags=set(m.get("tags") or [])
   s=8*("reasoning" in tags)+3*("tool-use" in tags)+min((m.get("context_window") or 0)/250000,4)
   s+=(m.get("released") or 0)/1e10
   return s
  c.sort(key=score,reverse=True)
  if c: selected.append(c[0])
 return selected[:cfg.get("max_models",6)]

def context():
 files=["docs/physics/FTOE_SO10_422_CLOSURE.md","docs/physics/FTOE_SO10_UV_OPERATOR_AND_THRESHOLD_GATES.md","physics/ftoe/uv_model_contract.json","physics/ftoe/g422_spectrum_registry.json"]
 out=[]
 for rel in files:
  p=ROOT/rel
  if p.exists(): out.append("\n--- "+rel+" ---\n"+p.read_text(errors="replace"))
 return "".join(out)[-60000:]

def ask(model,role,ctx,cfg):
 key=os.environ.get("AI_GATEWAY_API_KEY")
 prompt=("Falsification-first FToE research panel. Robert Frost is the manuscript author. "
         "Treat model output as advisory, distinguish verified/derived/proposed/failed, and never declare publication readiness without the repository gates. "
         "Return JSON with verdict,strongest_finding,failed_gates,next_gate,publication_blocker,proposed_patch.\nROLE="+role["name"]+"\n"+role["instruction"]+"\nSTATE:\n"+ctx)
 payload={"model":model,"messages":[{"role":"user","content":prompt}],"stream":False}
 res=http_json(cfg["gateway_base_url"]+"/chat/completions","POST",payload,key)
 text=res.get("choices",[{}])[0].get("message",{}).get("content","")
 try: return json.loads(text)
 except Exception: return {"raw":text}

def local_gates():
 rows=[]
 for cmd in ALLOWLIST:
  try:
   cp=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=1200)
   rows.append({"cmd":cmd,"rc":cp.returncode,"stdout":cp.stdout[-5000:],"stderr":cp.stderr[-5000:]})
  except Exception as e: rows.append({"cmd":cmd,"rc":127,"error":repr(e)})
  if rows[-1]["rc"] != 0: break
 return rows

def cycle(cfg):
 gates=local_gates(); emit("local_gates",gates)
 models=[]
 try: models=discover(cfg)
 except Exception as e: emit("model_discovery_error",{"error":repr(e)})
 if not models: emit("panel_degraded",{"reason":"no usable AI_GATEWAY_API_KEY/models; continuing local/GitHub gates"}); return
 emit("models",[{k:m.get(k) for k in ("id","name","released","context_window","tags")} for m in models])
 ctx=context()
 for i,role in enumerate(cfg["roles"]):
  m=models[i%len(models)]["id"]
  try: result=ask(m,role,ctx,cfg)
  except Exception as e: result={"error":repr(e)}
  emit("review",{"role":role["name"],"model":m,"result":result})

def stop_handler(*_):
 global RUNNING; RUNNING=False

def main():
 signal.signal(signal.SIGTERM,stop_handler); signal.signal(signal.SIGINT,stop_handler)
 cfg=json.loads(CONFIG.read_text())
 STATE.mkdir(parents=True,exist_ok=True)
 interval=max(300,int(os.environ.get("FTOE_AUTOPILOT_INTERVAL",1800)))
 emit("daemon_start",{"pid":os.getpid(),"author":"Robert Frost","interval_seconds":interval})
 while RUNNING and not STOP.exists():
  try: cycle(cfg)
  except Exception as e: emit("cycle_error",{"error":repr(e)})
  for _ in range(interval):
   if not RUNNING or STOP.exists(): break
   time.sleep(1)
 emit("daemon_stop",{"explicit_stop_file":STOP.exists()})
if __name__=="__main__": main()
