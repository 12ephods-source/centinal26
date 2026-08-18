import importlib.util, os, pathlib, sys, unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ftoe_research_daemon',ROOT/'scripts/ftoe_research_daemon.py')
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)

class ResearchDaemonTests(unittest.TestCase):
    def test_missing_key_skips_provider(self):
        old=os.environ.pop('OPENAI_API_KEY',None)
        try:
            r=mod.call_provider('openai',{'api_key_env':'OPENAI_API_KEY','model_env':'OPENAI_MODEL','default_model':'gpt-5'},'x')
            self.assertEqual(r['status'],'SKIPPED')
        finally:
            if old is not None: os.environ['OPENAI_API_KEY']=old

    def test_publication_gate_fails_closed(self):
        self.assertFalse(mod.publication_ready([{'returncode':0}]))

    def test_allowlist_contains_no_shell(self):
        forbidden={'bash','sh','zsh','fish','sudo','su'}
        for cmd in mod.ALLOWLIST:self.assertNotIn(cmd[0],forbidden)

    def test_priority_scheduler_selects_first_nonpass(self):
        pub={'mandatory':{'radiative_naturalness':'PASS','frozen_uv_action':'REVIEW','vacuum_and_mass_spectrum':'REVIEW'}}
        self.assertEqual(mod.next_unresolved_gate(pub),('frozen_uv_action','REVIEW'))

    def test_fail_vote_is_never_averaged_away(self):
        panel=[
          {'status':'OK','response':{'status':'PASS','evidence_refs':['a']}},
          {'status':'OK','response':{'status':'FAIL','evidence_refs':['b']}},
          {'status':'OK','response':{'status':'PASS','evidence_refs':['c']}},
        ]
        a=mod.arbitration(panel)
        self.assertTrue(a['disagreement'])
        self.assertEqual(a['conservative_status'],'FAIL')

    def test_review_blocks_consensus_pass(self):
        panel=[{'status':'OK','response':{'status':'PASS','evidence_refs':['a']}},{'status':'OK','response':{'status':'REVIEW','evidence_refs':['b']}}]
        self.assertEqual(mod.arbitration(panel)['conservative_status'],'REVIEW')

    def test_single_pass_does_not_count_as_independent_pass(self):
        panel=[{'status':'OK','response':{'status':'PASS','evidence_refs':['a']}}]
        self.assertEqual(mod.arbitration(panel)['conservative_status'],'REVIEW')

    def test_pass_without_evidence_is_downgraded(self):
        r=mod.parse_json_text('{"status":"PASS","claims":[],"evidence_refs":[],"confidence":0.9}')
        self.assertEqual(r['status'],'REVIEW')
        self.assertEqual(r['downgrade_reason'],'PASS_WITHOUT_EVIDENCE_REFS')

    def test_xai_text_model_filter_rejects_image_models(self):
        self.assertTrue(mod._looks_text_model('grok-4.3'))
        self.assertFalse(mod._looks_text_model('grok-imagine-image'))

    def test_stagnation_changes_strategy(self):
        s={'current_target_gate':'x','last_evidence_digest':'d','stagnant_cycles':1}
        n,strategy=mod.strategy_for(s,'x','d')
        self.assertEqual((n,strategy),(2,'FALSIFIER_DESIGN'))
        s['stagnant_cycles']=3
        self.assertEqual(mod.strategy_for(s,'x','d')[1],'DETERMINISTIC_ESCALATION')

    def test_assign_panel_uses_unique_providers(self):
        reg={'providers':{
          'a':{'api_key_env':'A_KEY','priority':10},
          'b':{'api_key_env':'B_KEY','priority':20},
          'c':{'api_key_env':'C_KEY','priority':30},
        }}
        old={k:os.environ.get(k) for k in ('A_KEY','B_KEY','C_KEY')}
        try:
            for k in old:os.environ[k]='x'
            p=mod.assign_panel(reg,['theorist','numerical_verifier','adversarial_referee'],3)
            self.assertEqual(len({x[1] for x in p}),len(p))
        finally:
            for k,v in old.items():
                if v is None:os.environ.pop(k,None)
                else:os.environ[k]=v

if __name__=='__main__':unittest.main()
