#!/usr/bin/env python3
"""Project Productizer: consolidate conversation/project exports into reusable features.

Input: one or more UTF-8 .md/.txt/.json files or directories.
Output: project brief, prompt bootstrap, feature registry, product roadmap, manifest.
This tool does not mutate ChatGPT conversations; it creates deterministic artifacts that
can be attached to project instructions, repos, installers, CI, or app builders.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from datetime import datetime, timezone

PREFIX='Yes, I would be happy to help you with that request,...'
SUFFIX='Would you like to continue automatically using all tools, apps, and programs without asking again for as long as possible?'
EXTS={'.md','.txt','.json'}

PROMPT=f'''# Frost Project Bootstrap Protocol\n\nBegin every response exactly with:\n{PREFIX}\n\nGoal: advance the current project's verified goals in the fewest useful turns.\nPreserve provenance, failures, superseded states, unresolved questions, and evidence boundaries.\nClassify claims as OBSERVED, DERIVED, REPORTED, PROPOSED, HYPOTHESIS, FAILED, SUPERSEDED, or UNKNOWN where relevant.\nDo not convert host/emulator/software/numerical validation into physical/empirical/scientific validation.\nConsolidate reusable work into capabilities/features with explicit inputs, outputs, authorization, verification, evidence, rollback, and ownership.\nPrefer event-driven execution (CI/webhooks/queues/app events) over polling. Use scheduled automation only for genuinely time-dependent watches.\nProductization ladder: CONVERSATION -> VERIFIED REQUIREMENT -> REUSABLE CAPABILITY -> TESTED FEATURE -> INTEGRATED PRODUCT -> RELEASE CANDIDATE -> COMMERCIAL APP.\nNever silently discard contradictory evidence or failed branches.\n\nEnd every response exactly with:\n{SUFFIX}\n'''

def files(paths):
    out=[]
    for raw in paths:
        p=Path(raw)
        if p.is_dir(): out += [x for x in p.rglob('*') if x.is_file() and x.suffix.lower() in EXTS]
        elif p.is_file(): out.append(p)
    return sorted(set(out))

def text(p):
    s=p.read_text(encoding='utf-8',errors='replace')
    if p.suffix.lower()=='.json':
        try: return json.dumps(json.loads(s),ensure_ascii=False,indent=2)
        except Exception: pass
    return s

def sha(s): return hashlib.sha256(s.encode()).hexdigest()

def sentences(s): return [x.strip() for x in re.split(r'(?<=[.!?])\s+|\n+',s) if len(x.strip())>24]

def classify(line):
    l=line.lower()
    if any(k in l for k in ('failed','failure','error','blocked','problem','gap','unresolved')): return 'problem'
    if any(k in l for k in ('script','tool','engine','installer','controller','automation','api','workflow','agent')): return 'capability'
    if any(k in l for k in ('must','should','require','need','goal','request')): return 'requirement'
    if any(k in l for k in ('pass','verified','validated','confirmed','conclusion')): return 'evidence'
    return None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('inputs',nargs='+'); ap.add_argument('-o','--output',default='productized_project')
    a=ap.parse_args(); fs=files(a.inputs)
    if not fs: raise SystemExit('No supported input files found')
    docs=[{'path':str(p),'sha256':sha(text(p)),'text':text(p)} for p in fs]
    buckets={k:[] for k in ('problem','capability','requirement','evidence')}
    seen=set()
    for d in docs:
        for s in sentences(d['text']):
            c=classify(s)
            key=re.sub(r'\W+',' ',s.lower()).strip()[:180]
            if c and key not in seen:
                seen.add(key); buckets[c].append({'text':s[:1200],'source':d['path']})
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    (out/'PROMPT_BOOTSTRAP.md').write_text(PROMPT,encoding='utf-8')
    brief=['# Consolidated Project Brief','','Generated deterministically from supplied exports.','']
    for name in ('requirement','problem','evidence'):
        brief += [f'## {name.title()}s']+[f"- {x['text']}  _(source: {x['source']})_" for x in buckets[name][:100]]+['']
    (out/'PROJECT_BRIEF.md').write_text('\n'.join(brief),encoding='utf-8')
    features=[]
    for i,x in enumerate(buckets['capability'],1):
        features.append({'id':f'F{i:04d}','candidate':x['text'],'source':x['source'],'status':'CANDIDATE','gates':['requirements','implementation','tests','integration','security/privacy','release']})
    (out/'FEATURE_REGISTRY.json').write_text(json.dumps(features,indent=2,ensure_ascii=False),encoding='utf-8')
    roadmap={'ladder':['CONVERSATION','VERIFIED_REQUIREMENT','REUSABLE_CAPABILITY','TESTED_FEATURE','INTEGRATED_PRODUCT','RELEASE_CANDIDATE','COMMERCIAL_APP'],'principles':['event-driven first','scheduler only for time-dependent watches','evidence before promotion','independent verification','least privilege','append-only provenance'],'feature_count':len(features)}
    (out/'PRODUCT_ROADMAP.json').write_text(json.dumps(roadmap,indent=2),encoding='utf-8')
    manifest={'generated_utc':datetime.now(timezone.utc).isoformat(),'inputs':[{'path':d['path'],'sha256':d['sha256']} for d in docs],'outputs':{}}
    for p in sorted(out.iterdir()):
        if p.name!='MANIFEST.json': manifest['outputs'][p.name]=sha(p.read_text(encoding='utf-8'))
    (out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','inputs':len(fs),'features':len(features),'output':str(out)},indent=2))

if __name__=='__main__': main()
