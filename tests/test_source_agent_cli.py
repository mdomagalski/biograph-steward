"""Operator CLI uses current saved source tools; all data/model outputs invented."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from biograph_steward.__main__ import main
from biograph_steward import source_agent
from biograph_steward.source_agent_jobs import read_source_agent_job
import test_source_agent as controller_fixture
import test_string_physical_source as source_fixture


class SourceAgentCliTests(unittest.TestCase):
    def setUp(self):
        f=source_fixture.NativePhysicalTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        _,self.source,_,self.graph=f.workspace();self.root=f.root
        self.before=self.inventory(self.source)
        self.question='Inspect candidate native STRING physical associations for UniProtKB:P04637.'

    def inventory(self,folder):
        return {p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*') if p.is_file()}

    def command(self,*args):
        out,error=StringIO(),StringIO()
        with redirect_stdout(out),redirect_stderr(error):code=main([str(a) for a in args])
        return code,json.loads(out.getvalue()) if out.getvalue() else None,error.getvalue()

    def test_current_protein_cohort_catalogue_never_uses_legacy_planner_or_calls_a_model(self):
        self.assertEqual(self.graph['scope']['kind'],'protein_cohort')
        with (patch.object(source_agent,'configured_source_agent_client',side_effect=AssertionError('No inference')),
              patch('biograph_steward.portability.BoundedQuestionWorkflow',side_effect=AssertionError('No legacy workflow'))):
            code,result,error=self.command('source-agent-catalogue','--run',self.source)
        self.assertEqual(code,0,error);self.assertEqual(result['scope']['kind'],'protein_cohort')
        self.assertEqual([t['name'] for t in result['tools']],['native_physical'])
        self.assertEqual(self.inventory(self.source),self.before)

    def test_operator_run_saves_real_tool_output_and_replay_never_calls_model(self):
        model=controller_fixture.FakeModel();trace=self.root/'operator_events'
        with patch.object(source_agent,'configured_source_agent_client',return_value=model):
            code,result,error=self.command('source-agent-run','--run',self.source,'--question',self.question,
                '--view','candidates','--max-results',8,'--trace-dir',trace)
        self.assertEqual(code,0,error);self.assertEqual(result['status'],'completed');self.assertEqual(result['model_calls'],3)
        job=read_source_agent_job(Path(result['job']),self.root)
        self.assertEqual(job['provider_kind'],'injected_test_model');self.assertFalse(job['actual_model_run'])
        self.assertEqual(result['provider_kind'],'injected_test_model');self.assertFalse(result['actual_model_run'])
        self.assertTrue(job['result']['focus_graph']['edges']);self.assertTrue(job['result']['inspections'][0]['passports'])
        events=[json.loads(p.read_text()) for p in sorted(trace.glob('event_*.json'))]
        self.assertEqual(events[0]['event'],'request_intent');self.assertEqual(events[-1]['event'],'model_response')
        with patch.object(source_agent,'configured_source_agent_client',side_effect=AssertionError('No inference in replay')):
            code,replayed,error=self.command('source-agent-verify','--job',result['job'],'--runs-dir',self.root)
        self.assertEqual(code,0,error);self.assertEqual(replayed['verification_model_calls'],0)
        self.assertEqual(replayed['recorded_model_calls'],3)
        self.assertEqual(self.inventory(self.source),self.before)

    def test_conflicting_flags_never_replace_the_explicit_constraints_object(self):
        constraints=self.root/'constraints.json';constraints.write_text(json.dumps({'view':'accepted'}))
        with patch.object(source_agent,'configured_source_agent_client',side_effect=AssertionError('No inference')):
            code,result,error=self.command('source-agent-run','--run',self.source,'--question',self.question,
                '--constraints',constraints,'--view','candidates')
        self.assertEqual(code,1);self.assertIsNone(result);self.assertIn('conflict',error)
        self.assertEqual(self.inventory(self.source),self.before)

    def test_boolean_constraint_cannot_be_silently_repaired_by_equal_integer_flag(self):
        constraints=self.root/'invalid_constraints.json';constraints.write_text(json.dumps({'max_results':True}))
        with patch.object(source_agent,'configured_source_agent_client',side_effect=AssertionError('No inference on invalid bool')):
            code,result,error=self.command('source-agent-run','--run',self.source,'--question',self.question,
                '--constraints',constraints,'--max-results',1)
        self.assertEqual(code,1);self.assertIsNone(result);self.assertIn('conflict',error)
        self.assertEqual(self.inventory(self.source),self.before)

    def test_progress_never_overwrites_prior_records_or_enters_immutable_source(self):
        old=self.root/'old_events';old.mkdir();(old/'prior.txt').write_text('preserve')
        for destination in [old,self.source/'new_events']:
            with self.subTest(destination=destination),patch.object(source_agent,'configured_source_agent_client',side_effect=AssertionError('No inference')):
                code,result,error=self.command('source-agent-run','--run',self.source,'--question',self.question,'--trace-dir',destination)
            self.assertEqual(code,1);self.assertIsNone(result)
        self.assertEqual((old/'prior.txt').read_text(),'preserve');self.assertEqual(self.inventory(self.source),self.before)

    def test_guard_only_job_retains_zero_call_attribution(self):
        with patch.object(source_agent,'configured_source_agent_client',side_effect=AssertionError('No model factory')):
            code,result,error=self.command('source-agent-run','--run',self.source,'--question',
                'Which proteins directly bind UniProtKB:P04637 in pull-down assays?')
        self.assertEqual(code,0,error);self.assertEqual(result['status'],'scope_rejected')
        self.assertEqual(result['model_calls'],0)
        job=read_source_agent_job(Path(result['job']),self.root)
        self.assertTrue(job['result']['trace']['preflight_blocked']);self.assertFalse(job['actual_model_run'])
        self.assertEqual(self.inventory(self.source),self.before)


if __name__=='__main__':unittest.main()
