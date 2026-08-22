from __future__ import annotations

import json
from pathlib import Path

def b(v): return v is True

def eval_guard(t,c):
    r=[]
    if t=='exact_quote_source' and c.get('is_exact_quote') and not (c.get('source_type') in {'raw_message','raw_file','tool_record','provider_record'} and c.get('source_locator') and c.get('source_hash')): r.append('unauthenticated exact quote')
    elif t=='derivative_independence' and int(c.get('required_independent_sources',2))>len(set(c.get('root_source_ids',[]))): r.append('insufficient independent roots')
    elif t=='original_vs_reconstruction' and c.get('claimed_status') in {'RECOVERED_ORIGINAL','CANONICAL_ORIGINAL'} and not (b(c.get('byte_identity_verified')) or b(c.get('authenticated_original_provenance'))): r.append('original status lacks original proof')
    elif t=='completion_verification' and c.get('claimed_status') in {'VERIFIED','PRODUCTION_READY'} and not (b(c.get('execution_success')) and b(c.get('independent_verifier_pass'))): r.append('execution is not independently verified')
    elif t=='physical_device_gate' and c.get('claimed_status') in {'DEVICE_VALIDATED','PERSISTENT_VALIDATED','AUTONOMOUS_VALIDATED'} and not (b(c.get('authentic_device_origin')) and b(c.get('independent_device_verification'))): r.append('physical evidence missing')
    elif t=='stale_continuation' and c.get('next_action_state') in {'completed','merged','superseded','rejected'}: r.append('stale next action')
    elif t=='authorization_capability' and b(c.get('mutation_requested')) and not (b(c.get('authorization_valid')) and b(c.get('capability_allowed')) and c.get('authorization_status')=='AUTHORIZED'): r.append('authorization/capability invalid')
    elif t=='independent_verifier' and b(c.get('independent_claim')) and (c.get('producer_identity')==c.get('verifier_identity') or b(c.get('shared_verification_core')) or not b(c.get('attestation_bound'))): r.append('verifier independence not established')
    elif t=='device_origin_attestation' and b(c.get('device_origin_claim')) and (b(c.get('origin_fields_caller_controlled')) or not b(c.get('external_origin_anchor'))): r.append('device origin self-asserted')
    elif t=='failure_receipt' and b(c.get('attempt_started')) and not b(c.get('terminal_receipt_written')): r.append('terminal receipt missing')
    elif t=='exit_code_gate' and ((b(c.get('tests_failed')) and c.get('exit_code')==0) or (b(c.get('tests_passed')) and c.get('exit_code') not in {0,None})): r.append('test result/exit mismatch')
    elif t=='raw_bytes_hash' and b(c.get('byte_integrity_claim')) and c.get('hash_basis')!='raw_bytes': r.append('not hashing raw bytes')
    elif t=='manifest_bijection' and any(b(c.get(k)) for k in ('duplicate_archive_paths','manifest_member_mismatch','hash_mismatch','output_self_ingested')): r.append('package bijection/provenance failure')
    elif t=='semantic_verification' and b(c.get('verified_claim')) and (b(c.get('only_self_consistency_checked')) or not b(c.get('independent_semantic_predicate'))): r.append('semantic correctness not independently checked')
    elif t=='receipt_binding' and b(c.get('receipt_present')) and not all(b(c.get(k)) for k in ('request_hash_matches','service_matches','operation_matches','nested_receipts_validated')): r.append('receipt not bound')
    elif t=='expiry_recheck' and b(c.get('durable_transition')) and not all(b(c.get(k)) for k in ('authorization_current','request_identity_stable','attestation_identity_stable')): r.append('durable-transition recheck failed')
    elif t=='packaged_dependency' and b(c.get('release_claim')) and (b(c.get('repo_relative_dependency')) or not b(c.get('clean_install_test_pass'))): r.append('package dependency/clean-install failure')
    elif t=='bounded_capture' and b(c.get('subprocess_capture')) and not b(c.get('stream_bounded')): r.append('unbounded subprocess capture')
    elif t=='lineage_evidence' and c.get('lineage_claim') in {'CANONICAL','ORIGINAL','SUPERSEDES'} and (c.get('basis') in {'version_string','modified_timestamp'} or not b(c.get('provenance_edge_verified'))): r.append('lineage not provenance-grounded')
    elif t=='tool_success_receipt' and c.get('success_claim') in {'DONE','TESTED','VERIFIED','COMPLETE','PERSISTED'} and (c.get('required_tool_status') in {'timeout','failed','interrupted','unknown'} or not b(c.get('successful_readback'))): r.append('success claimed without successful tool/readback')
    elif t=='external_mutation_auth' and b(c.get('external_mutation')) and not (b(c.get('explicit_action_verb')) and b(c.get('explicit_target')) and b(c.get('current_authorization'))): r.append('external mutation lacks explicit authorization')
    elif t=='reproducible_build' and b(c.get('reproducible_claim')) and (b(c.get('wall_clock_in_identity')) or not b(c.get('stable_input_derived_identity'))): r.append('nondeterministic build identity')
    return {'result':'BLOCK' if r else 'PASS','reasons':r}


if __name__ == '__main__':
    import argparse
    import hashlib
    from collections import defaultdict, deque

    def canon(o): return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    def verify_event(e):
        x=dict(e); got=x.pop('event_id',None); return got=='evt_sha256_'+hashlib.sha256(canon(x)).hexdigest()
    def load_events(root):
        ev=[]
        for p in sorted(Path(root).glob('events/*/*.jsonl')):
            for n,line in enumerate(p.read_text().splitlines(),1):
                if line.strip():
                    e=json.loads(line)
                    if not verify_event(e): raise SystemExit(f'bad event hash {p}:{n}')
                    ev.append(e)
        return ev
    def projection(root):
        events=load_events(root); by={}
        for e in events:
            k=e['mistake_class_id']; d=by.setdefault(k,{'mistake_class_id':k,'mistake_class':e['mistake_class'],'occurrence_count':0,'verified_occurrence_count':0,'event_ids':[]})
            d['occurrence_count']+=1; d['event_ids'].append(e['event_id'])
            if e.get('verification_status')=='VERIFIED': d['verified_occurrence_count']+=1
        return {'authoritative':False,'source':'content-hashed immutable event batches','event_count':len(events),'class_count':len(by),'classes':[by[k] for k in sorted(by)]}
    MAP={'EXACT_QUOTE':['exact_quote_source'],'ORIGINAL_FILE':['original_vs_reconstruction','raw_bytes_hash'],'VERIFICATION_CLAIM':['completion_verification','independent_verifier','semantic_verification','tool_success_receipt'],'PHYSICAL_DEVICE_CLAIM':['physical_device_gate','device_origin_attestation'],'EXTERNAL_MUTATION':['authorization_capability','external_mutation_auth','expiry_recheck'],'PACKAGE_RELEASE':['manifest_bijection','packaged_dependency','reproducible_build','exit_code_gate'],'RECEIPT_VALIDATION':['receipt_binding'],'CONTINUATION':['stale_continuation'],'SUBPROCESS':['failure_receipt','bounded_capture'],'LINEAGE':['lineage_evidence']}
    def preflight(req):
        selected=[]
        for k in req.get('kinds',[]): selected += MAP.get(k,[])
        selected=list(dict.fromkeys(selected)); ctx=req.get('context',{}); rr=[]
        for t in selected:
            z=eval_guard(t,ctx.get(t,ctx)); z['guard_type']=t; rr.append(z)
        return {'result':'BLOCK' if any(z['result']=='BLOCK' for z in rr) else 'PASS','interception_scope':'instrumented_tool_and_artifact_pipelines_only','selected_guards':selected,'results':rr,'review_heuristic_ids':req.get('review_heuristic_ids',[])}
    def taint(graph,roots):
        o=defaultdict(list)
        for e in graph.get('edges',[]):
            if e.get('predicate') in {'DERIVED_FROM','TRANSFORMED_FROM','SUMMARIZES','COPIES','USES_CLAIM'}: o[e['source_id']].append(e['target_id'])
        q=deque(roots); seen=set(roots)
        while q:
            x=q.popleft()
            for y in o.get(x,[]):
                if y not in seen: seen.add(y); q.append(y)
        return {'tainted_ids':sorted(seen),'scope':'explicit_edges_only','unknown_outside_graph':True}
    def evaluate(root):
        cases=json.loads((Path(root)/'tests/holdout_cases.json').read_text()); failures=[]
        for c in cases:
            got=eval_guard(c['guard_type'],c['context'])['result']
            if got!=c['expected']: failures.append({'guard_id':c['guard_id'],'expected':c['expected'],'got':got})
        return {'suite':'holdout_adversarial_v1','case_count':len(cases),'failures':failures,'result':'PASS' if not failures else 'FAIL'}

    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('project'); p.add_argument('root',nargs='?',default='.')
    p=sub.add_parser('preflight'); p.add_argument('request')
    p=sub.add_parser('taint'); p.add_argument('graph'); p.add_argument('roots',nargs='+')
    p=sub.add_parser('evaluate'); p.add_argument('root',nargs='?',default='.')
    a=ap.parse_args()
    if a.cmd=='project': result=projection(a.root)
    elif a.cmd=='preflight': result=preflight(json.loads(Path(a.request).read_text()))
    elif a.cmd=='taint': result=taint(json.loads(Path(a.graph).read_text()),a.roots)
    else: result=evaluate(a.root)
    print(json.dumps(result,indent=2))
    if a.cmd in {'preflight','evaluate'} and result['result']!='PASS': raise SystemExit(2)
