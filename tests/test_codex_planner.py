"""Isolated CLI contract tests; no real model or authentication used."""
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from biograph_steward.codex_planner import CodexPlanner, DISABLED_FEATURES
from biograph_steward.graph import build_graph
from biograph_steward.planning import PlannerUnavailable, configured_planner
from test_civic import fixture
from test_planning import civic_plan


def events():
    return [{'type': 'thread.started'}, {'type': 'turn.started'},
            {'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'PRIVATE TEST REASONING'}},
            {'type': 'item.completed', 'item': {'type': 'agent_message'}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 20, 'output_tokens': 30}}]


class CodexPlanningTests(unittest.TestCase):
    def setUp(self):
        p, c = fixture(); self.graph = build_graph(p, civic_snapshot=c)
        self.which = patch('biograph_steward.codex_planner.shutil.which', return_value='/test/codex')
        self.which.start(); self.addCleanup(self.which.stop)

    def runner(self, plan=None, stream=None, failure=None, calls=None):
        def run(args, **kwargs):
            if args[-1] == '--version':
                return subprocess.CompletedProcess(args, 0, 'codex-cli 1.2.3\n', '')
            if calls is not None: calls.append((args, kwargs))
            if failure: raise failure
            Path(args[args.index('--output-last-message') + 1]).write_text(json.dumps(plan or civic_plan()))
            return subprocess.CompletedProcess(args, 0, '\n'.join(json.dumps(e) for e in (events() if stream is None else stream)), 'SECRET STDERR')
        return run

    def test_empty_workspace_tool_disabled_single_turn_and_no_secrets_or_labels(self):
        calls=[]
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'TEST-SECRET', 'BIOGRAPH_PLANNER_API_KEY': 'OTHER-SECRET'}):
            trace=CodexPlanner(model='test-model', runner=self.runner(calls=calls)).plan('Inspect candidates', self.graph)
        self.assertEqual(trace['status'], 'validated'); self.assertEqual(trace['model_calls'], 1)
        self.assertEqual(trace['planner_kind'], 'injected_test_model'); self.assertEqual(len(calls), 1)
        args, kwargs=calls[0]
        self.assertIn('--ignore-user-config', args); self.assertIn('--ephemeral', args)
        self.assertEqual(args[args.index('--sandbox')+1], 'read-only')
        self.assertEqual({args[i+1] for i, a in enumerate(args) if a=='--disable'}, set(DISABLED_FEATURES))
        self.assertIn('web_search="disabled"', args); self.assertNotIn('TEST-SECRET', json.dumps(kwargs))
        self.assertNotIn('reference_plan', kwargs['input']); self.assertNotIn('INVENTED SOFTWARE TEST statement', kwargs['input'])
        self.assertFalse(Path(args[args.index('--cd')+1]).exists())
        for value in ['SECRET STDERR', 'PRIVATE TEST REASONING', 'OTHER-SECRET']:
            self.assertNotIn(value, json.dumps(trace))
        self.assertIsNone(trace['model_returned']); self.assertIsNone(trace['transport_requests'])

    def test_tool_unknown_event_incomplete_duplicate_turn_and_malformed_events_fail_closed(self):
        streams=[events()+[{'type':'item.completed','item':{'type':'command_execution','command':'bad'}}],
                 events()+[{'type':'new.unknown'}], events()[:-1], events()+[{'type':'turn.completed'}],
                 [None], [{'type':None}], [{'type':'item.completed','item':[]}]]
        for stream in streams:
            trace=CodexPlanner(model='test', runner=self.runner(stream=stream)).plan('Question', self.graph)
            self.assertEqual(trace['status'], 'planner_error'); self.assertIsNone(trace['plan'])
            self.assertNotIn('command', json.dumps(trace))

    def test_scope_violation_is_invalid_and_no_second_turn_repairs_it(self):
        plan=civic_plan(profile='CIViC.molecularprofile:999'); calls=[]
        trace=CodexPlanner(model='test', runner=self.runner(plan=plan,calls=calls)).plan('Question', self.graph)
        self.assertEqual(trace['status'], 'invalid_plan'); self.assertIsNone(trace['plan']); self.assertEqual(len(calls), 1)

    def test_timeout_and_launch_failure_are_sanitized_without_retry(self):
        for failure in [subprocess.TimeoutExpired('SECRET-COMMAND', 90), OSError('SECRET-ERROR')]:
            calls=[]
            trace=CodexPlanner(model='test',runner=self.runner(failure=failure,calls=calls)).plan('Question',self.graph)
            self.assertEqual(trace['status'],'planner_error'); self.assertIsNone(trace['plan']); self.assertEqual(len(calls),1)
            self.assertNotIn('SECRET',json.dumps(trace))

    def test_explicit_provider_model_and_executable_no_silent_auth_fallback(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(PlannerUnavailable):CodexPlanner()
            with self.assertRaises(PlannerUnavailable):configured_planner()
        with patch.dict('os.environ',{'BIOGRAPH_PLANNER_PROVIDER':'unknown'}):
            with self.assertRaises(PlannerUnavailable):configured_planner()
        with patch.dict('os.environ',{'BIOGRAPH_PLANNER_PROVIDER':'codex'}), patch('biograph_steward.codex_planner.CodexPlanner',return_value='explicit'):
            self.assertEqual(configured_planner(),'explicit')
        with patch('biograph_steward.codex_planner.shutil.which',return_value=None):
            with self.assertRaises(PlannerUnavailable):CodexPlanner(model='test')
        with self.assertRaises(PlannerUnavailable):CodexPlanner(model='bad\nmodel')


if __name__=='__main__':unittest.main()
