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
        self.assertFalse(mod.publication_ready([{'returncode':0}],[]))

    def test_allowlist_contains_no_shell(self):
        forbidden={'bash','sh','zsh','fish','sudo','su'}
        for cmd in mod.ALLOWLIST:self.assertNotIn(cmd[0],forbidden)

    def test_priority_scheduler_selects_first_nonpass(self):
        pub={'mandatory':{'radiative_naturalness':'PASS','frozen_uv_action':'REVIEW','vacuum_and_mass_spectrum':'REVIEW'}}
        self.assertEqual(mod.next_unresolved_gate(pub),('frozen_uv_action','REVIEW'))

    def test_fail_vote_is_never_averaged_away(self):
        panel=[
          {'status':'OK','response':{'status':'PASS'}},
          {'status':'OK','response':{'status':'FAIL'}},
          {'status':'OK','response':{'status':'PASS'}},
        ]
        a=mod.arbitration(panel)
        self.assertTrue(a['disagreement'])
        self.assertEqual(a['conservative_status'],'FAIL')

    def test_review_blocks_consensus_pass(self):
        panel=[{'status':'OK','response':{'status':'PASS'}},{'status':'OK','response':{'status':'REVIEW'}}]
        self.assertEqual(mod.arbitration(panel)['conservative_status'],'REVIEW')

if __name__=='__main__':unittest.main()
