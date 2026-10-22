"""Current product exports and retired workflow boundaries; invented data only."""
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from zipfile import ZipFile

from biograph_steward.__main__ import main
from biograph_steward.graph import save_run
from biograph_steward.planning import ModelPlanner
from biograph_steward.webapp import create_server, login_return_path
from test_civic import fixture
from test_planning import abstain_plan, civic_plan, response


class ActiveWorkflowHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.snapshot, civic = fixture()
        save_run(self.snapshot, self.root/'graph', civic_snapshot=civic)
        self.server = create_server(0, self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, body=None):
        headers = {'Content-Type': 'application/json'} if body is not None else {}
        try:
            result = self.opener.open(Request(self.base+path, headers=headers,
                data=json.dumps(body).encode() if body is not None else None), timeout=5)
        except HTTPError as exc:
            result = exc
        with result:
            return result.status, result.headers, result.read()

    def post(self, path, body):
        status, _, content = self.request(path, body)
        self.assertEqual(status, 200, content)
        return json.loads(content)

    def download(self, name):
        status, headers, content = self.request('/api/download/'+name)
        self.assertEqual(status, 200, content)
        self.assertEqual(headers['Content-Type'], 'application/zip')
        self.assertIn('attachment', headers['Content-Disposition'])
        with ZipFile(BytesIO(content)) as archive:
            self.assertTrue(all(path.startswith(name+'/') for path in archive.namelist()))
            return {path[len(name)+1:]: archive.read(path) for path in archive.namelist()}

    def plan(self, transport):
        planner = ModelPlanner(model='invented-model', endpoint='http://localhost:9999',
                               transport=transport)
        with patch('biograph_steward.planning.configured_planner', return_value=planner):
            return self.post('/api/plan', {'run_id': 'graph', 'question': 'Inspect invented candidates.'})

    def test_current_graph_and_question_exports_preserve_saved_evidence(self):
        graph_files = self.download('graph')
        self.assertEqual(json.loads(graph_files['snapshot.json']), self.snapshot)
        self.assertIn('graph.json', graph_files)
        self.assertIn('civic_snapshot.json', graph_files)
        question = self.post('/api/therapy-question', {'run_id': 'graph', 'view': 'candidates'})
        question_files = self.download(question['question_id'])
        self.assertEqual(json.loads(question_files['question.json']), question['answer'])
        self.assertIn('summary.txt', question_files)
        self.assertIn('evidence_context.tsv', question_files)

    def test_valid_planner_answers_and_abstentions_remain_downloadable(self):
        for proposal, answered in [(civic_plan(), True), (abstain_plan(), False)]:
            with self.subTest(answered=answered):
                planned = self.plan(lambda _, proposal=proposal: response(proposal))
                self.assertEqual(planned['trace']['status'], 'validated')
                files = self.download(planned['plan_id'])
                self.assertEqual(json.loads(files['planner_trace.json']), planned['trace'])
                self.assertEqual(json.loads(files['execution.json'])['status'], planned['status'])
                self.assertEqual('answer/question.json' in files, answered)
                if answered:
                    self.assertEqual(json.loads(files['answer/question.json']), planned['answer'])

    def test_failed_model_calls_and_invalid_plans_preserve_downloadable_traces(self):
        def failed_transport(_):
            raise OSError('Invented unavailable model')
        invalid = response(civic_plan())
        invalid['output'][0]['content'][0]['text'] = 'not JSON'
        for transport, expected in [(failed_transport, 'planner_error'),
                                    (lambda _: invalid, 'invalid_plan')]:
            with self.subTest(status=expected):
                planned = self.plan(transport)
                self.assertEqual(planned['trace']['status'], expected)
                self.assertIsNone(planned['answer'])
                files = self.download(planned['plan_id'])
                self.assertEqual(set(files), {'planner_trace.json'})
                self.assertEqual(json.loads(files['planner_trace.json']), planned['trace'])

    def test_question_and_nested_planner_answer_corruption_is_rejected(self):
        question = self.post('/api/therapy-question', {'run_id': 'graph', 'view': 'candidates'})
        planned = self.plan(lambda _: response(civic_plan()))
        for name, relative in [(question['question_id'], 'question.json'),
                               (planned['plan_id'], 'answer/question.json')]:
            with self.subTest(artifact=name):
                path = self.root/name/relative
                answer = json.loads(path.read_text())
                answer['overview'] = 'Changed after the saved answer hash was computed.'
                path.write_text(json.dumps(answer))
                status, headers, _ = self.request('/api/download/'+name)
                self.assertEqual(status, 400)
                self.assertNotEqual(headers['Content-Type'], 'application/zip')

    def test_retired_reports_and_actions_are_absent_with_historical_files_present(self):
        historical = self.root/'historical'; historical.mkdir()
        (historical/'report.html').write_text('<h1>Historical report must stay archived</h1>')
        (historical/'metrics.json').write_text('{}')
        routes = ['/api/evidence-quality', '/api/source-facts', '/api/biomedbert-status',
                  '/api/biomedbert-checks', '/api/evaluation/historical/',
                  '/api/source-facts/historical/', '/api/fact-check/historical/',
                  '/api/biomedbert-check/historical/']
        for route in routes:
            with self.subTest(route=route):
                status, _, content = self.request(route)
                self.assertEqual(status, 404)
                self.assertNotIn(b'Historical report must stay archived', content)
                self.assertEqual(login_return_path(route), '/')
        for route in ['/api/fact-check', '/api/biomedbert-check']:
            with self.subTest(action=route):
                self.assertEqual(self.request(route, {})[0], 404)
        status, _, page = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'id="plannerPanel"', page)
        self.assertIn(b'id="refreshPanel"', page)
        for route in ['/api/evidence-quality', '/api/source-facts', '/api/biomedbert-check']:
            self.assertNotIn(route.encode(), page)

    def test_retired_or_unrecognized_downloads_cannot_fall_back_to_an_unchecked_zip(self):
        for name, marker in [('quality', 'metrics.json'), ('source_facts', 'source_fact_manifest.json'),
                             ('biomedbert', 'biomedbert_manifest.json'), ('unknown', 'arbitrary.json')]:
            with self.subTest(artifact=name):
                folder = self.root/name; folder.mkdir()
                (folder/marker).write_text('{}')
                (folder/'report.html').write_text('Unverified historical or unrelated output')
                # Even a real snapshot cannot make a retired study a current product run.
                if name != 'unknown':
                    (folder/'run_manifest.json').write_text((self.root/'graph/run_manifest.json').read_text())
                    (folder/'snapshot.json').write_text((self.root/'graph/snapshot.json').read_text())
                status, headers, content = self.request('/api/download/'+name)
                self.assertEqual(status, 400)
                self.assertNotEqual(headers['Content-Type'], 'application/zip')
                self.assertNotIn(b'Unverified historical or unrelated output', content)

    def test_symlinked_run_files_and_directories_cannot_enter_exports(self):
        with tempfile.TemporaryDirectory() as outside:
            outside = Path(outside)
            (outside/'secret.txt').write_text('Invented private sentinel')
            (self.root/'alias').symlink_to(self.root/'graph', target_is_directory=True)
            (self.root/'outside').symlink_to(outside, target_is_directory=True)
            for name in ['alias', 'outside']:
                self.assertEqual(self.request('/api/download/'+name)[0], 404)
            for name, target, directory in [('linked.txt', outside/'secret.txt', False),
                                            ('linked_directory', outside, True)]:
                with self.subTest(link=name):
                    link = self.root/'graph'/name
                    link.symlink_to(target, target_is_directory=directory)
                    status, headers, content = self.request('/api/download/graph')
                    self.assertEqual(status, 400)
                    self.assertNotEqual(headers['Content-Type'], 'application/zip')
                    self.assertNotIn(b'Invented private sentinel', content)
                    link.unlink()

    def test_unknown_planner_status_does_not_make_an_artifact_downloadable(self):
        folder = self.root/'unknown_planner'; folder.mkdir()
        (folder/'planner_trace.json').write_text(json.dumps({'status': 'old_experiment_result'}))
        self.assertEqual(self.request('/api/download/unknown_planner')[0], 400)


class ActiveWorkflowCliTests(unittest.TestCase):
    def test_help_exposes_current_commands_and_rejects_retired_experiments(self):
        help_text = StringIO()
        with redirect_stdout(help_text), self.assertRaises(SystemExit) as stopped:
            main(['--help'])
        self.assertEqual(stopped.exception.code, 0)
        for command in ['refresh-compare', 'therapy-question', 'plan-question', 'identifier-registry']:
            self.assertIn(command, help_text.getvalue())
        for command in ['evaluation-run', 'growth-compare', 'source-fact-check', 'biomedbert-check']:
            with self.subTest(command=command), redirect_stderr(StringIO()):
                self.assertNotIn(command, help_text.getvalue())
                with self.assertRaises(SystemExit) as stopped:
                    main([command])
                self.assertEqual(stopped.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
