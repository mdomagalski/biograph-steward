"""Deployment operator checks, using invented data and local HTTP endpoints."""
from contextlib import contextmanager, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from biograph_steward.__main__ import main
from biograph_steward.client import digest
from biograph_steward.deployment_smoke import DeploymentClient, run_smoke
from biograph_steward.webapp import create_server
from test_portability import TOKEN, chat, mock_model


@contextmanager
def deployed(runs, token=TOKEN):
    server = create_server(0, runs, access_token=token)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown(); server.server_close(); thread.join()


def plan_response(payload, view='candidates'):
    data = json.loads(payload['messages'][1]['content'])
    catalogue = data['catalogue']
    protein = next(p for p in catalogue['proteins'] if p['symbol'] == 'DEMO_P1')
    plan = {'action': 'query', 'tool': 'protein_neighborhood', 'disease_id': catalogue['pharos_disease']['id'],
            'protein_id': protein['id'], 'profile_id': None, 'therapy': None,
            'relations': ['shared_pathways'], 'view': view, 'reason': 'Invented smoke scope.'}
    return 200, {}, json.dumps(chat(plan)).encode()


class DeploymentSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'BIOGRAPH_ACCESS_TOKEN': TOKEN,
                                          'NO_PROXY': '127.0.0.1,localhost,::1',
                                          'no_proxy': '127.0.0.1,localhost,::1'}, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)

    def test_saved_data_and_answer_reopen_after_server_restart_without_new_writes(self):
        runs = self.root/'data'
        with deployed(runs) as url:
            report = run_smoke(url, self.root/'first')
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['reported_model_calls'], 0)
        self.assertEqual(len(list(runs.iterdir())), 2)
        before = {str(p.relative_to(runs)): p.read_bytes() for p in runs.rglob('*') if p.is_file()}
        with deployed(runs) as url:
            reopened = run_smoke(url, self.root/'reopened', receipt=self.root/'first/report.json')
        self.assertEqual(reopened['status'], 'passed')
        self.assertEqual(reopened['initial_receipt_sha256'], report['receipt_sha256'])
        self.assertFalse(reopened['restart_independently_attested'])
        self.assertEqual(before, {str(p.relative_to(runs)): p.read_bytes() for p in runs.rglob('*') if p.is_file()})
        self.assertNotIn(TOKEN, json.dumps(report) + json.dumps(reopened))

    def test_live_http_planner_uses_one_turn_and_matches_the_deterministic_scope(self):
        with mock_model(plan_response) as (endpoint, calls), patch.dict(os.environ, {
            'BIOGRAPH_MODEL_PROVIDER': 'nim', 'BIOGRAPH_MODEL_ID': 'invented-smoke-model',
            'BIOGRAPH_MODEL_ENDPOINT': endpoint, 'BIOGRAPH_MODEL_API_KEY': TOKEN}):
            with deployed(self.root/'data') as url:
                report = run_smoke(url, self.root/'smoke', with_planner=True)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['planner_kind'], 'live_nim'); self.assertEqual(len(calls), 1)
        self.assertEqual(report['reported_model_calls'], 1); self.assertEqual(report['planner_http_requests'], 1)
        trace = json.loads((self.root/'smoke/planner_trace.json').read_text())
        self.assertEqual(trace['status'], 'validated')
        self.assertNotIn(TOKEN, json.dumps(report) + json.dumps(trace))

    def test_valid_plan_for_a_different_view_fails_without_a_second_turn(self):
        with mock_model(lambda payload: plan_response(payload, view='accepted')) as (endpoint, calls):
            with patch.dict(os.environ, {'BIOGRAPH_MODEL_PROVIDER': 'nim', 'BIOGRAPH_MODEL_ID': 'test',
                                         'BIOGRAPH_MODEL_ENDPOINT': endpoint}):
                with deployed(self.root/'data') as url:
                    report = run_smoke(url, self.root/'bad_scope', with_planner=True)
        self.assertEqual(report['status'], 'failed'); self.assertEqual(len(calls), 1)
        self.assertEqual(report['checks'][-1]['check'], 'one_bounded_model_plan')
        self.assertIn('different scope', report['checks'][-1]['reason'])
        self.assertEqual(report['reported_model_calls'], 1)

    def test_credential_failure_is_retained_and_never_creates_a_source(self):
        with deployed(self.root/'data', token='different-invented-workspace-token') as url:
            with redirect_stdout(io.StringIO()) as output:
                code = main(['deployment-smoke', '--base-url', url, '--out', str(self.root/'failure')])
        self.assertEqual(code, 1)
        self.assertEqual(list((self.root/'data').iterdir()), [])
        self.assertEqual(json.loads(output.getvalue())['checks'][-1]['check'], 'authentication')
        self.assertNotIn(TOKEN, (self.root/'failure/report.json').read_text())

    def test_reopening_changed_saved_answers_fails_instead_of_claiming_persistence(self):
        runs = self.root/'data'
        with deployed(runs) as url:
            first = run_smoke(url, self.root/'first')
            answer_path = runs/first['question_id']/'question.json'
            answer = json.loads(answer_path.read_text()); answer['overview'] = 'Altered after the initial check.'
            answer['answer_sha256'] = digest({k: v for k, v in answer.items() if k != 'answer_sha256'})
            answer_path.write_text(json.dumps(answer))
            result = run_smoke(url, self.root/'changed', receipt=self.root/'first/report.json')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['checks'][-1]['check'], 'saved_answer_reopens')

    def test_receipt_and_existing_outputs_are_checked_before_requests(self):
        with deployed(self.root/'data') as url:
            run_smoke(url, self.root/'first')
            with self.assertRaises(FileExistsError): run_smoke(url, self.root/'first')
            with self.assertRaises(ValueError):
                run_smoke(url, self.root/'unused', receipt=self.root/'first/report.json', with_planner=True)
            receipt = json.loads((self.root/'first/report.json').read_text())
            receipt['source_run'] = '../other'
            receipt['receipt_sha256'] = digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'})
            (self.root/'tampered.json').write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):
                run_smoke(url, self.root/'unused', receipt=self.root/'tampered.json')
        self.assertFalse((self.root/'unused').exists())

    def test_unprotected_loopback_is_allowed_and_invalid_remote_settings_are_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with deployed(self.root/'data', token=None) as url:
                report = run_smoke(url, self.root/'local')
            self.assertEqual(report['status'], 'passed'); self.assertFalse(report['authentication_required'])
            with self.assertRaises(ValueError): DeploymentClient('https://workspace.example.org')
        for url in ['http://remote.example.org', 'https://user:private@example.org',
                    'https://example.org/path', 'https://example.org?token=private']:
            with self.assertRaises(ValueError): DeploymentClient(url)

    def test_deployment_redirect_cannot_forward_workspace_credentials(self):
        calls = []
        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                calls.append(self.path); self.send_response(307)
                self.send_header('Location', '/unexpected'); self.end_headers()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            report = run_smoke(f'http://127.0.0.1:{server.server_port}', self.root/'redirect')
        finally:
            server.shutdown(); server.server_close(); thread.join()
        self.assertEqual(report['status'], 'failed'); self.assertEqual(calls, ['/healthz'])
        self.assertIn('307', report['checks'][-1]['reason'])


if __name__ == '__main__':
    unittest.main()
