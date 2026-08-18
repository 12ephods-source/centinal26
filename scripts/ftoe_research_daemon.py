#!/usr/bin/env python3
"""Bounded autonomous FToE research orchestrator v2.

Principles:
- deterministic gates are authoritative;
- LLMs propose/audit, never publish or merge;
- execute only named local gates;
- route to the highest-value unresolved publication gate;
- discover provider models when supported and keep model IDs overridable;
- escalate on cross-model disagreement instead of averaging it away.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, pathlib, random, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'physics/ftoe/llm_provider_registry.json'
STATE=ROOT/'physics/ftoe/autonomous_research_state.json'
PUB=ROOT/'physics/ftoe/publication_gate.json'
ART=ROOT/'artifacts/ftoe-research-agent'

ALLOWLIST=[
 ['python','scripts/ftoe_so10_group_theory_gate.py'],
 ['python','scripts/ftoe_so10_naturalness_gate.py','--MU','2.04990990688745e16','--muI','9.54e3','--alphaU','0.032067325570772874'],
 ['python','-m','unittest','tests.test_ftoe_so10_group_theory_gate','-v'],
 ['python','-m','unittest','tests.test_ftoe_so10_422_gate','-v'],
 ['python','-m','unittest','tests.test_ftoe_so10_uv_closure','-v'],
]

GATE_PRIORITY=[
 'radiative_naturalness','frozen_uv_action','vacuum_and_mass_spectrum',
 'operator_basis_and_C_eff','two_loop_rge_with_derived_thresholds',
 'proton_decay_from_frozen_spectrum','dark_sector_joint_viability',
 'inflation_joint_likelihood','microscopic_L4_derivation',
 'manuscript_claim_audit','reproducibility_bundle'
]

GATE_ROLES={
 'radiative_naturalness':['theorist','group_theory_auditor','adversarial_referee'],
 'frozen_uv_action':['theorist','group_theory_auditor','adversarial_referee'],
 'vacuum_and_mass_spectrum':['theorist','numerical_verifier','group_theory_auditor'],
 'operator_basis_and_C_eff':['group_theory_auditor','theorist','adversarial_referee'],
 'two_loop_rge_with_derived_thresholds':['numerical_verifier','phenomenology_auditor','adversarial_referee'],
 'proton_decay_from_frozen_spectrum':['phenomenology_auditor','numerical_verifier','adversarial_referee'],
 'dark_sector_joint_viability':['phenomenology_auditor','adversarial_referee'],
 'inflation_joint_likelihood':['phenomenology_auditor','numerical_verifier','adversarial_referee'],
 'microscopic_L4_derivation':['theorist','adversarial_referee'],
 'manuscript_claim_audit':['adversarial_referee','manuscript_editor'],
 'reproducibility_bundle':['numerical_verifier','manuscript_editor']
}

ROLE_PROMPTS={
 'theorist':'Construct the smallest mechanism that closes this gate without retuning existing outputs. Give equations, parameter count, symmetry assumptions, and explicit kill conditions.',
 'group_theory_auditor':'Derive rather than assume representation content, invariants, Casimirs/Dynkin indices, Clebsches and forbidden operators. Flag every uncomputed contraction.',
 'phenomenology_auditor':'Attack the candidate with current observational/experimental constraints and identify the first falsifier. Do not repair a failed branch unless the failure itself demands a new mechanism.',
 'numerical_verifier':'Audit conditioning, equations, boundary conditions, uncertainty, independent reproduction and numerical-vs-theoretical error. Reject target-driven tuning.',
 'adversarial_referee':'Act as a hostile journal referee. Locate circularity, hidden fitting, underdetermination, omitted operators, unfrozen choices and publication blockers.',
 'literature_synthesizer':'State which primary-source results are required to close or kill this gate. Separate literature facts from FToE-specific assumptions.',
 'manuscript_editor':'Use only verified/derived claims. Remove or label anything still REVIEW/FAIL; never convert plausibility into a result.'
}

SYSTEM='''You are one independent member of a theoretical-physics review panel. You cannot authorize publication. Return JSON only with keys status (PASS|REVIEW|FAIL), claims, evidence_needed, falsifiers, next_actions, confidence. Never invent execution results, papers, citations, or derived coefficients.'''

def load_json(p,d):
    try:return json.loads(p.read_text())
    except Exception:return d

def save_json(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.tmp'); t.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n'); t.replace(p)

def http_json(method,url,headers=None,payload=None,timeout=180,retries=3):
    data=None if payload is None else json.dumps(payload).encode()
    hdr={'Accept':'application/json',**(headers or {})}
    if data is not None: hdr['Content-Type']='application/json'
    for attempt in range(retries+1):
        try:
            req=urllib.request.Request(url,data=data,headers=hdr,method=method)
            with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code not in (408,409,429,500,502,503,504) or attempt>=retries: raise
            delay=min(60,(2**attempt)+random.random()); time.sleep(delay)
        except (urllib.error.URLError,TimeoutError):
            if attempt>=retries: raise
            time.sleep(min(60,(2**attempt)+random.random()))

def discover_models(name,cfg,key):
    """Best-effort authenticated discovery. Failure never blocks an overridden/default model."""
    try:
        if name=='openai':
            x=http_json('GET','https://api.openai.com/v1/models',{'Authorization':f'Bearer {key}'})
            return [m['id'] for m in x.get('data',[]) if m.get('id')]
        if name=='gemini':
            x=http_json('GET','https://generativelanguage.googleapis.com/v1beta/models?key='+urllib.parse.quote(key))
            return [m.get('baseModelId') or m.get('name','').removeprefix('models/') for m in x.get('models',[]) if 'generateContent' in m.get('supportedGenerationMethods',[])]
        if name=='xai':
            x=http_json('GET','https://api.x.ai/v1/language-models',{'Authorization':f'Bearer {key}'})
            return [m['id'] for m in x.get('data',[]) if m.get('id')]
        if name=='deepseek':
            x=http_json('GET','https://api.deepseek.com/models',{'Authorization':f'Bearer {key}'})
            return [m['id'] for m in x.get('data',[]) if m.get('id')]
        if name=='mistral':
            x=http_json('GET','https://api.mistral.ai/v1/models',{'Authorization':f'Bearer {key}'})
            return [m['id'] for m in x.get('data',[]) if m.get('id')]
    except Exception:
        return []
    return []

def choose_model(name,cfg,key):
    override=os.getenv(cfg['model_env'])
    if override:return override,False
    available=discover_models(name,cfg,key)
    prefs=cfg.get('preferred_models',[cfg.get('default_model')])
    for p in prefs:
        if p and (not available or p in available): return p,bool(available)
    if available:return available[0],True
    return cfg.get('default_model'),False

def parse_json_text(text):
    try:return json.loads(text)
    except Exception:
        a=text.find('{'); b=text.rfind('}')
        if 0<=a<b:
            try:return json.loads(text[a:b+1])
            except Exception:pass
        return {'status':'REVIEW','raw':text[:20000]}

def call_provider(name,cfg,prompt):
    key=os.getenv(cfg['api_key_env'])
    if not key:return {'provider':name,'status':'SKIPPED','reason':'missing key'}
    model,discovered=choose_model(name,cfg,key)
    try:
        if name=='openai':
            x=http_json('POST','https://api.openai.com/v1/responses',{'Authorization':f'Bearer {key}'},{'model':model,'input':SYSTEM+'\n\n'+prompt,'store':False})
            text=x.get('output_text','') or '\n'.join(c.get('text','') for i in x.get('output',[]) for c in i.get('content',[]) if c.get('text'))
        elif name=='anthropic':
            x=http_json('POST','https://api.anthropic.com/v1/messages',{'x-api-key':key,'anthropic-version':'2023-06-01'},{'model':model,'max_tokens':5000,'system':SYSTEM,'messages':[{'role':'user','content':prompt}]})
            text='\n'.join(c.get('text','') for c in x.get('content',[]) if c.get('type')=='text')
        elif name=='gemini':
            x=http_json('POST',f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',{'x-goog-api-key':key},{'contents':[{'parts':[{'text':SYSTEM+'\n\n'+prompt}]}]})
            text='\n'.join(p.get('text','') for c in x.get('candidates',[]) for p in c.get('content',{}).get('parts',[]))
        elif name in {'xai','deepseek','mistral'}:
            url={'xai':'https://api.x.ai/v1/chat/completions','deepseek':'https://api.deepseek.com/chat/completions','mistral':'https://api.mistral.ai/v1/chat/completions'}[name]
            body={'model':model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':prompt}],'temperature':0.2}
            if name=='deepseek': body.update({'thinking':{'type':'enabled'},'reasoning_effort':'high','response_format':{'type':'json_object'}})
            x=http_json('POST',url,{'Authorization':f'Bearer {key}'},body)
            text=x['choices'][0]['message'].get('content','')
        elif name=='cohere':
            x=http_json('POST','https://api.cohere.com/v2/chat',{'Authorization':f'Bearer {key}'},{'model':model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':prompt}],'stream':False})
            text='\n'.join(c.get('text','') for c in x.get('message',{}).get('content',[]) if c.get('type')=='text')
        else:return {'provider':name,'status':'SKIPPED','reason':'unsupported'}
        return {'provider':name,'model':model,'model_discovered':discovered,'status':'OK','response':parse_json_text(text)}
    except Exception as e:return {'provider':name,'model':model,'status':'ERROR','error':type(e).__name__+': '+str(e)[:500]}

def run_gate(cmd):
    p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=900)
    return {'cmd':cmd,'returncode':p.returncode,'stdout':p.stdout[-20000:],'stderr':p.stderr[-10000:]}

def next_unresolved_gate(pub):
    m=pub.get('mandatory',{})
    for k in GATE_PRIORITY:
        if m.get(k)!='PASS':return k,m.get(k,'UNKNOWN')
    return 'manuscript_claim_audit',m.get('manuscript_claim_audit','UNKNOWN')

def rank_providers(reg,role):
    configured=[]
    for name,cfg in reg.get('providers',{}).items():
        if os.getenv(cfg['api_key_env']):configured.append((int(cfg.get('priority',50)),name,cfg))
    configured.sort()
    # Diversity first: cap normal role at two models; hard/referee roles at three.
    n=3 if role in {'adversarial_referee','theorist','group_theory_auditor'} else 2
    return configured[:n]

def arbitration(panel):
    ok=[p for p in panel if p.get('status')=='OK']
    statuses=[p.get('response',{}).get('status','REVIEW') for p in ok]
    counts={s:statuses.count(s) for s in ('PASS','REVIEW','FAIL')}
    disagreement=len({s for s in statuses if s in counts})>1
    # Any FAIL is preserved; no majority vote can erase it.
    conservative='FAIL' if counts['FAIL'] else ('REVIEW' if counts['REVIEW'] or disagreement else ('PASS' if counts['PASS'] else 'REVIEW'))
    return {'responses':len(ok),'counts':counts,'disagreement':disagreement,'conservative_status':conservative}

def publication_ready(gates,panel):
    pub=load_json(PUB,{})
    deterministic=all(g['returncode']==0 for g in gates)
    explicit=pub.get('status')=='PASS' and all(v=='PASS' for v in pub.get('mandatory',{}).values())
    manuscript=(ROOT/'docs/physics/FTOE_PUBLICATION_DRAFT.md').exists()
    return bool(deterministic and explicit and manuscript)

def cycle():
    reg=load_json(REGISTRY,{})
    state=load_json(STATE,{'cycle':0,'publication_ready':False})
    pub=load_json(PUB,{})
    target,target_status=next_unresolved_gate(pub)
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=ART/stamp; out.mkdir(parents=True,exist_ok=True)
    gates=[run_gate(c) for c in ALLOWLIST]
    gate_digest=hashlib.sha256(json.dumps(pub,sort_keys=True).encode()).hexdigest()
    context={'cycle':state.get('cycle',0)+1,'target_gate':target,'target_status':target_status,'publication_gate_digest':gate_digest,'gate_summary':[{'cmd':g['cmd'],'returncode':g['returncode']} for g in gates],'constraint':'Close or kill exactly one highest-value gate; do not add unconstrained parameters.'}
    roles=GATE_ROLES.get(target,['adversarial_referee','theorist'])
    max_calls=max(1,int(os.getenv('FTOE_MAX_LLM_CALLS_PER_CYCLE','8'))); calls=0; panel=[]
    for role in roles:
        task=f'TARGET GATE: {target} ({target_status})\n'+ROLE_PROMPTS[role]+'\n\nMachine context:\n'+json.dumps(context,sort_keys=True)
        for _,name,cfg in rank_providers(reg,role):
            if calls>=max_calls:break
            r=call_provider(name,cfg,task); r['role']=role; panel.append(r); calls+=1
        if calls>=max_calls:break
    arb=arbitration(panel)
    # Escalate one extra referee model only when there is genuine disagreement and budget remains.
    if arb['disagreement'] and calls<max_calls:
        used={p.get('provider') for p in panel}
        candidates=[x for x in rank_providers(reg,'adversarial_referee') if x[1] not in used]
        if candidates:
            _,name,cfg=candidates[0]
            r=call_provider(name,cfg,'Resolve this panel disagreement conservatively. Do not average incompatible claims.\n'+json.dumps({'target':target,'panel':panel},sort_keys=True)[:80000]); r['role']='tie_break_referee'; panel.append(r); calls+=1; arb=arbitration(panel)
    ready=publication_ready(gates,panel)
    record={'schema':'FTOE-RESEARCH-CYCLE-v2','timestamp':stamp,'target_gate':target,'context':context,'gates':gates,'panel':panel,'arbitration':arb,'llm_calls':calls,'publication_ready':ready}
    raw=json.dumps(record,indent=2,sort_keys=True)+'\n'; (out/'cycle.json').write_text(raw); (out/'SHA256.txt').write_text(hashlib.sha256(raw.encode()).hexdigest()+'  cycle.json\n')
    state.update({'cycle':context['cycle'],'last_cycle':stamp,'publication_ready':ready,'current_target_gate':target,'last_arbitration':arb,'last_artifact':str(out.relative_to(ROOT))})
    save_json(STATE,state)
    return 0 if all(g['returncode']==0 for g in gates) else 2

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--once',action='store_true'); ap.add_argument('--interval',type=int,default=int(os.getenv('FTOE_AGENT_INTERVAL','3600'))); a=ap.parse_args()
    while True:
        cycle()
        if load_json(STATE,{}).get('publication_ready'):return
        if a.once:return
        time.sleep(max(300,a.interval))
if __name__=='__main__':main()
