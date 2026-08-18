#!/usr/bin/env python3
"""Bounded autonomous FToE research orchestrator.

Runs repeated research/verification cycles using configured LLM APIs, but never
publishes, merges, or executes arbitrary shell. Deterministic local gates remain
authoritative; model outputs are advisory evidence only.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, pathlib, subprocess, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "physics/ftoe/llm_provider_registry.json"
STATE = ROOT / "physics/ftoe/autonomous_research_state.json"
ART = ROOT / "artifacts/ftoe-research-agent"

ALLOWLIST = [
    ["python", "scripts/ftoe_so10_group_theory_gate.py"],
    ["python", "scripts/ftoe_so10_naturalness_gate.py", "--MU", "2.04990990688745e16", "--muI", "9.54e3", "--alphaU", "0.032067325570772874"],
    ["python", "-m", "unittest", "tests.test_ftoe_so10_group_theory_gate", "-v"],
    ["python", "-m", "unittest", "tests.test_ftoe_so10_422_gate", "-v"],
    ["python", "-m", "unittest", "tests.test_ftoe_so10_uv_closure", "-v"],
]

ROLE_PROMPTS = {
 "theorist":"Construct the smallest UV completion consistent with the frozen FToE SO(10)->G422->SM branch. Do not retune established outputs. Identify equations, assumptions, and kill conditions.",
 "group_theory_auditor":"Audit SO(10)/Pati-Salam representations, invariant contractions, beta coefficients, Clebsches, and operator selection. Prefer explicit derivations over plausibility arguments.",
 "phenomenology_auditor":"Attack the candidate with proton decay, vacuum stability, collider, dark-sector, cosmology, and precision constraints. Return falsifiers before repairs.",
 "numerical_verifier":"Review numerical methodology, conditioning, boundary conditions, independent checks, and uncertainty. Distinguish solver residual from theory uncertainty.",
 "adversarial_referee":"Act as a hostile journal referee. Find circularity, hidden fitting, unsupported claims, missing calculations, and reasons the work is not publishable.",
 "literature_synthesizer":"Identify which exact external results are needed to justify or falsify the current closure branch. Separate established literature facts from proposed FToE extensions.",
 "manuscript_editor":"Given only verified/derived claims, propose a publication-ready structure. Mark every unclosed statement as REVIEW rather than smoothing over it."
}

SYSTEM = """You are one member of a multi-model theoretical-physics review panel. You cannot authorize publication. Return concise JSON with keys: status (PASS|REVIEW|FAIL), claims, evidence_needed, falsifiers, next_actions. Never invent execution results or citations."""


def load_json(path, default):
    try: return json.loads(path.read_text())
    except Exception: return default

def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)

def post_json(url, payload, headers, timeout=180):
    data=json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json",**headers},method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode())

def extract_openai(x):
    if x.get("output_text"): return x["output_text"]
    parts=[]
    for item in x.get("output",[]):
        for c in item.get("content",[]):
            if c.get("text"): parts.append(c["text"])
    return "\n".join(parts)

def call_provider(name, cfg, prompt):
    key=os.getenv(cfg["api_key_env"])
    if not key: return {"provider":name,"status":"SKIPPED","reason":"missing key"}
    model=os.getenv(cfg["model_env"],cfg["default_model"])
    try:
        if name=="openai":
            x=post_json("https://api.openai.com/v1/responses",{"model":model,"input":SYSTEM+"\n\n"+prompt,"store":False},{"Authorization":f"Bearer {key}"})
            text=extract_openai(x)
        elif name=="anthropic":
            x=post_json("https://api.anthropic.com/v1/messages",{"model":model,"max_tokens":5000,"system":SYSTEM,"messages":[{"role":"user","content":prompt}]},{"x-api-key":key,"anthropic-version":"2023-06-01"})
            text="\n".join(c.get("text","") for c in x.get("content",[]) if c.get("type")=="text")
        elif name=="gemini":
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            x=post_json(url,{"contents":[{"parts":[{"text":SYSTEM+"\n\n"+prompt}]}]},{"x-goog-api-key":key})
            text="\n".join(p.get("text","") for c in x.get("candidates",[]) for p in c.get("content",{}).get("parts",[]))
        elif name in {"xai","deepseek","mistral"}:
            base={"xai":"https://api.x.ai/v1/chat/completions","deepseek":"https://api.deepseek.com/chat/completions","mistral":"https://api.mistral.ai/v1/chat/completions"}[name]
            x=post_json(base,{"model":model,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],"temperature":0.2},{"Authorization":f"Bearer {key}"})
            text=x["choices"][0]["message"].get("content","")
        elif name=="cohere":
            x=post_json("https://api.cohere.com/v2/chat",{"model":model,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],"stream":False},{"Authorization":f"Bearer {key}"})
            text="\n".join(c.get("text","") for c in x.get("message",{}).get("content",[]) if c.get("type")=="text")
        else: return {"provider":name,"status":"SKIPPED","reason":"unsupported"}
        try: parsed=json.loads(text)
        except Exception: parsed={"status":"REVIEW","raw":text}
        return {"provider":name,"model":model,"status":"OK","response":parsed}
    except Exception as e:
        return {"provider":name,"model":model,"status":"ERROR","error":type(e).__name__+": "+str(e)[:500]}

def run_gate(cmd):
    p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=900)
    return {"cmd":cmd,"returncode":p.returncode,"stdout":p.stdout[-20000:],"stderr":p.stderr[-10000:]}

def publication_ready(gates, panel):
    # Fail closed. LLM agreement is never sufficient.
    required=[g["returncode"]==0 for g in gates]
    manuscript=(ROOT/"docs/physics/FTOE_PUBLICATION_DRAFT.md").exists()
    mandatory=(ROOT/"physics/ftoe/publication_gate.json")
    gate=load_json(mandatory,{})
    explicit=gate.get("status")=="PASS" and all(v=="PASS" for v in gate.get("mandatory",{}).values())
    return bool(required and all(required) and manuscript and explicit)

def cycle():
    reg=load_json(REGISTRY,{})
    state=load_json(STATE,{"cycle":0,"publication_ready":False})
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out=ART/stamp; out.mkdir(parents=True,exist_ok=True)
    gates=[run_gate(c) for c in ALLOWLIST]
    context={"cycle":state.get("cycle",0)+1,"gate_summary":[{"cmd":g["cmd"],"returncode":g["returncode"]} for g in gates],"current_goal":"Close one falsifiable gap toward a publishable FToE manuscript without adding unconstrained parameters."}
    panel=[]
    for role in reg.get("roles",[]):
        task=ROLE_PROMPTS[role]+"\n\nMachine context:\n"+json.dumps(context,sort_keys=True)
        for name,cfg in reg.get("providers",{}).items():
            r=call_provider(name,cfg,task); r["role"]=role; panel.append(r)
    ready=publication_ready(gates,panel)
    record={"schema":"FTOE-RESEARCH-CYCLE-v1","timestamp":stamp,"gates":gates,"panel":panel,"publication_ready":ready}
    raw=json.dumps(record,indent=2,sort_keys=True)+"\n"; (out/"cycle.json").write_text(raw)
    (out/"SHA256.txt").write_text(hashlib.sha256(raw.encode()).hexdigest()+"  cycle.json\n")
    state.update({"cycle":context["cycle"],"last_cycle":stamp,"publication_ready":ready,"last_artifact":str(out.relative_to(ROOT))})
    save_json(STATE,state)
    return 0 if all(g["returncode"]==0 for g in gates) else 2

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--once",action="store_true"); ap.add_argument("--interval",type=int,default=int(os.getenv("FTOE_AGENT_INTERVAL",3600)))
    a=ap.parse_args()
    while True:
        cycle()
        if load_json(STATE,{}).get("publication_ready"): return
        if a.once: return
        time.sleep(max(300,a.interval))
if __name__=="__main__": main()
