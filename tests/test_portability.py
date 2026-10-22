"""Portable hosting and HTTP model contracts; all model/source records invented."""
import base64
from contextlib import contextmanager, redirect_stdout
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from biograph_steward.__main__ import main
from biograph_steward.graph import save_run
from biograph_steward.model_transport import JSONModelClient, ModelUnavailable
from biograph_steward.planning import ModelPlanner, configured_planner
from biograph_steward.portability import BoundedQuestionWorkflow, runtime_status
from biograph_steward.runtime import AccessPolicy, runs_directory, cache_directory
from biograph_steward.webapp import create_server
from test_civic import fixture
from test_planning import civic_plan, response

TOKEN = 'invented-workspace-token-for-tests-only'


def chat(value):
    return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': json.dumps(value)}}],
            'model': 'test-returned-model', 'usage': {'prompt_tokens': 12, 'completion_tokens': 20}}


@contextmanager
def mock_model(reply):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append({'payload': payload, 'authorization': self.headers.get('Authorization')})
            status, headers, body = reply(payload)
            self.send_response(status)
            for k, v in headers.items(): self.send_header(k, v)
            self.end_headers(); self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1/chat/completions', calls
    finally:
        server.shutdown(); server.server_close(); thread.join()


class ModelTransportTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'NO_PROXY': '127.0.0.1,localhost,::1',
                                          'no_proxy': '127.0.0.1,localhost,::1'}, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)
        p, c = fixture(); from biograph_steward.graph import build_graph
        self.graph = build_graph(p, civic_snapshot=c)

    def test_nim_planner_uses_bounded_http_protocol(self):
        def reply(payload):
            return 200, {}, json.dumps(chat(civic_plan())).encode()
        with mock_model(reply) as (endpoint, calls), patch.dict(os.environ, {'BIOGRAPH_MODEL_API_KEY': TOKEN}):
            planner = ModelPlanner(model='test-model', endpoint=endpoint, provider='nim')
            trace = planner.plan('Inspect invented candidates.', self.graph)
        self.assertEqual(trace['status'], 'validated')
        self.assertEqual(trace['planner_kind'], 'live_nim')
        self.assertEqual(len(calls), 1)
        for call in calls:
            self.assertEqual(call['authorization'], 'Bearer ' + TOKEN)
            self.assertIn('guided_json', call['payload']); self.assertIn('max_tokens', call['payload'])
            for forbidden in ('store', 'max_completion_tokens', 'tools', 'tool_choice'):
                self.assertNotIn(forbidden, call['payload'])
        self.assertEqual(trace['model_calls'], 1); self.assertEqual(trace['transport_requests'], 1)
        self.assertNotIn(TOKEN, json.dumps(trace))

    def test_role_settings_override_shared_values_without_provider_fallback(self):
        env = {'BIOGRAPH_MODEL_PROVIDER': 'nim', 'BIOGRAPH_MODEL_ID': 'shared-model',
               'BIOGRAPH_MODEL_ENDPOINT': 'http://localhost:9999/v1/chat/completions',
               'BIOGRAPH_PLANNER_MODEL': 'planner-model', 'BIOGRAPH_PLANNER_API': 'chat_completions',
               'BIOGRAPH_PLANNER_MAX_OUTPUT_TOKENS': '2000'}
        with patch.dict(os.environ, env):
            planner = configured_planner()
            self.assertEqual(planner.model, 'planner-model')
            self.assertEqual(planner.api, 'chat_completions')
            self.assertEqual(planner.max_output_tokens, 2000)
        with patch.dict(os.environ, {'BIOGRAPH_PLANNER_PROVIDER': 'unknown'}):
            with self.assertRaises(ModelUnavailable):
                configured_planner()

    def test_tool_attempts_and_truncated_outputs_fail_without_repair(self):
        tool = chat(civic_plan()); tool['choices'][0]['message']['tool_calls'] = [{'name': 'shell'}]
        long = chat(civic_plan()); long['choices'][0]['finish_reason'] = 'length'
        for raw in [tool, long]:
            calls = []
            def transport(payload): calls.append(payload); return raw
            trace = ModelPlanner(model='test', endpoint='http://localhost:9999', provider='nim', transport=transport).plan('Question', self.graph)
            self.assertEqual(trace['status'], 'invalid_plan'); self.assertIsNone(trace['plan']); self.assertEqual(len(calls), 1)

    def test_redirect_does_not_forward_credentials_or_make_a_second_request(self):
        with mock_model(lambda _: (200, {}, json.dumps(chat(civic_plan())).encode())) as (target, second):
            with mock_model(lambda _: (307, {'Location': target}, b'PRIVATE ERROR BODY')) as (endpoint, first):
                with patch.dict(os.environ, {'BIOGRAPH_MODEL_API_KEY': TOKEN}):
                    trace = ModelPlanner(model='test', endpoint=endpoint, provider='nim').plan('Question', self.graph)
        self.assertEqual(len(first), 1); self.assertEqual(len(second), 0)
        self.assertEqual(trace['status'], 'planner_error')
        self.assertNotIn('PRIVATE', json.dumps(trace)); self.assertNotIn(TOKEN, json.dumps(trace))

    def test_local_model_keys_are_not_sent_to_an_environment_proxy(self):
        with mock_model(lambda _: (500, {}, b'Proxy must not receive this request')) as (proxy_url, proxy_calls):
            with mock_model(lambda _: (200, {}, json.dumps(chat(civic_plan())).encode())) as (endpoint, calls):
                proxy = proxy_url.removesuffix('/v1/chat/completions')
                with patch.dict(os.environ, {'HTTP_PROXY': proxy, 'http_proxy': proxy, 'NO_PROXY': '', 'no_proxy': '',
                                              'BIOGRAPH_MODEL_API_KEY': TOKEN}):
                    trace = ModelPlanner(model='test', endpoint=endpoint, provider='nim').plan('Question', self.graph)
        self.assertEqual(trace['status'], 'validated'); self.assertEqual(len(calls), 1); self.assertEqual(proxy_calls, [])

    def test_http_errors_and_oversized_envelopes_are_bounded_and_sanitized(self):
        for code, body in [(500, b'PRIVATE ERROR BODY'), (200, b'X' * 1_000_002)]:
            with mock_model(lambda _, c=code, b=body: (c, {}, b)) as (endpoint, calls):
                trace = ModelPlanner(model='test', endpoint=endpoint, provider='nim').plan('Question', self.graph)
            self.assertEqual(trace['status'], 'planner_error'); self.assertEqual(len(calls), 1)
            self.assertNotIn('PRIVATE', json.dumps(trace)); self.assertIsNone(trace['plan'])

    def test_responses_rejects_tool_items_and_private_reasoning_is_not_saved(self):
        raw = response(civic_plan()); raw['output'].insert(0, {'type': 'reasoning', 'text': 'PRIVATE REASONING'})
        model = ModelPlanner(model='test', endpoint='http://localhost:9999', transport=lambda _: raw)
        trace = model.plan('Question', self.graph)
        self.assertEqual(trace['status'], 'validated'); self.assertNotIn('PRIVATE REASONING', json.dumps(trace))
        raw['output'].append({'type': 'function_call', 'name': 'shell'})
        self.assertEqual(model.plan('Question', self.graph)['status'], 'invalid_plan')

    def test_unsafe_urls_and_bad_budgets_are_rejected_before_requests(self):
        for endpoint in ['http://remote.example/v1', 'https://user:secret@example.org/v1',
                         'https://example.org/v1?key=secret', 'https://example.org/v1#secret',
                         'https://example.org:99999/v1', 'https://example.org/with space']:
            with self.assertRaises(ModelUnavailable): ModelPlanner(model='test', endpoint=endpoint)
        for key, value in [('MAX_OUTPUT_TOKENS', '1'), ('MAX_OUTPUT_TOKENS', 'invalid'), ('TIMEOUT', '301')]:
            with patch.dict(os.environ, {f'BIOGRAPH_MODEL_{key}': value}):
                with self.assertRaises(ModelUnavailable): ModelPlanner(model='test', endpoint='http://localhost:9999')
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'OPENAI-ONLY-TEST'}):
            self.assertIsNone(ModelPlanner(model='test', endpoint='https://custom.example.org').key)

    def test_timeout_is_one_failed_turn_without_repair_or_secret_exception_text(self):
        calls = []
        def timeout(payload):
            calls.append(payload); raise TimeoutError('PRIVATE EXCEPTION')
        trace = ModelPlanner(model='test', endpoint='http://localhost:9999', provider='nim', transport=timeout).plan('Question', self.graph)
        self.assertEqual(trace['status'], 'planner_error'); self.assertIsNone(trace['plan'])
        self.assertEqual(len(calls), 1); self.assertNotIn('PRIVATE EXCEPTION', json.dumps(trace))


class HostingTests(unittest.TestCase):
    def test_cli_restart_reopens_runs_from_the_configured_persistent_directory(self):
        with tempfile.TemporaryDirectory() as root:
            env = {k: v for k, v in os.environ.items() if not k.startswith('BIOGRAPH_')}
            env.update(BIOGRAPH_DATA_DIR=root, BIOGRAPH_ACCESS_TOKEN=TOKEN)
            @contextmanager
            def app():
                proc = subprocess.Popen([sys.executable, '-m', 'biograph_steward', 'serve', '--port', '0', '--no-browser'],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                try:
                    line = proc.stdout.readline().strip()
                    self.assertTrue(line.startswith('BioGraph Steward: http://127.0.0.1:'), line)
                    yield line.split(': ', 1)[1]
                finally:
                    proc.terminate(); proc.communicate(timeout=10)
            headers = {'Authorization': 'Bearer '+TOKEN, 'Content-Type': 'application/json'}
            with app() as url:
                with urlopen(Request(url+'/api/build', data=b'{"mode":"demo"}', headers=headers), timeout=5) as r:
                    saved = json.load(r)
            self.assertTrue((Path(root)/'runs'/saved['run_id']/'snapshot.json').is_file())
            with app() as url:
                with urlopen(Request(url+'/api/run/'+saved['run_id'], headers=headers), timeout=5) as r:
                    reopened = json.load(r)
                self.assertEqual(reopened['graph']['snapshot_sha256'], saved['graph']['snapshot_sha256'])

    def test_data_paths_and_role_diagnostics_do_not_expose_secrets_or_call_models(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            'BIOGRAPH_DATA_DIR': root, 'BIOGRAPH_HOST': '0.0.0.0', 'BIOGRAPH_ACCESS_TOKEN': TOKEN,
            'BIOGRAPH_MODEL_PROVIDER': 'nim', 'BIOGRAPH_MODEL_ID': 'test',
            'BIOGRAPH_MODEL_ENDPOINT': 'http://localhost:9999/v1/chat/completions', 'BIOGRAPH_MODEL_API_KEY': TOKEN}, clear=True):
            with patch.object(JSONModelClient, 'generate') as generate:
                status = runtime_status(); generate.assert_not_called()
            self.assertEqual(runs_directory(), Path(root)/'runs'); self.assertEqual(cache_directory(), Path(root)/'cache')
            self.assertTrue(status['planner']['configuration_valid']); self.assertNotIn('verifier', status)
            self.assertNotIn(TOKEN, json.dumps(status)); self.assertFalse((Path(root)/'runs').exists())
            with patch.dict(os.environ, {'BIOGRAPH_RUNS_DIR': root+'/other'}):
                self.assertEqual(runs_directory(), Path(root)/'other')

    def test_nonlocal_bind_and_remote_origins_require_authentication(self):
        for args in [{'host': '0.0.0.0'}, {'allowed_origins': ['https://workspace.example.org']}]:
            with self.assertRaisesRegex(ValueError, 'ACCESS_TOKEN'): AccessPolicy(**args)
        for token in ['', 'short', 'token with spaces'*4]:
            with self.assertRaises(ValueError): AccessPolicy(access_token=token)
        for origin in ['*', 'https://workspace.example.org/path', 'https://user:secret@example.org', 'http://remote.example.org']:
            with self.assertRaises(ValueError): AccessPolicy(allowed_origins=[origin], access_token=TOKEN)

    def test_exact_origins_and_basic_or_bearer_tokens(self):
        p = AccessPolicy(allowed_origins=['https://workspace.example.org'], access_token=TOKEN)
        self.assertTrue(p.allows_origin('https://workspace.example.org:443', 8766))
        self.assertTrue(p.allows_origin('http://127.0.0.1:8766', 8766))
        for origin in ['https://other.example.org', 'https://workspace.example.org.evil', 'http://localhost:8767', 'null']:
            self.assertFalse(p.allows_origin(origin, 8766))
        self.assertTrue(p.authenticated('Bearer '+TOKEN))
        basic = base64.b64encode(('steward:'+TOKEN).encode()).decode()
        self.assertTrue(p.authenticated('Basic '+basic))
        for auth in [None, 'Bearer wrong', 'Basic !bad', 'Basic '+base64.b64encode(('other:'+TOKEN).encode()).decode()]:
            self.assertFalse(p.authenticated(auth))

    def test_protected_web_ui_and_approved_proxy_origin_preserve_local_workflow(self):
        with tempfile.TemporaryDirectory() as root:
            server = create_server(0, Path(root), access_token=TOKEN, allowed_origins=['https://workspace.example.org'])
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(url+'/healthz') as r: self.assertEqual(json.load(r)['status'], 'ok')
                with self.assertRaises(HTTPError) as ctx: urlopen(url+'/api/planner')
                self.assertEqual(ctx.exception.code, 401)
                auth = {'Authorization': 'Basic '+base64.b64encode(('steward:'+TOKEN).encode()).decode()}
                with urlopen(Request(url, headers=auth)) as r: self.assertIn('BioGraph', r.read().decode())
                headers = {'Authorization': 'Bearer '+TOKEN, 'Content-Type': 'application/json', 'Origin': 'https://workspace.example.org'}
                with urlopen(Request(url+'/api/build', data=b'{"mode":"demo"}', headers=headers)) as r:
                    result = json.load(r); self.assertEqual(result['graph']['data_kind'], 'synthetic_demo')
                files = sorted(Path(root).iterdir())
                for changed, code in [({'Origin': 'https://evil.example.org'}, 403), ({'Authorization': 'Bearer wrong'}, 401)]:
                    with self.assertRaises(HTTPError) as ctx:
                        urlopen(Request(url+'/api/build', data=b'{"mode":"demo"}', headers={**headers, **changed}))
                    self.assertEqual(ctx.exception.code, code); self.assertEqual(sorted(Path(root).iterdir()), files)
                with tempfile.TemporaryDirectory() as outside:
                    (Path(outside)/'private.txt').write_text('INVENTED OUTSIDE CONTENT')
                    (Path(root)/'outside').symlink_to(outside, target_is_directory=True)
                    with self.assertRaises(HTTPError) as ctx:
                        urlopen(Request(url+'/api/download/outside', headers=headers))
                    self.assertEqual(ctx.exception.code, 404)
            finally:
                server.shutdown(); server.server_close(); thread.join()

    def test_invalid_hosting_configuration_is_a_nonzero_sanitized_diagnostic(self):
        with patch.dict(os.environ, {'BIOGRAPH_HOST': '0.0.0.0'}, clear=True), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['runtime-check']), 2)
        self.assertFalse(json.loads(output.getvalue())['hosting']['valid'])


class WorkflowTests(unittest.TestCase):
    def test_fixed_source_one_plan_one_query_and_no_source_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            p, c = fixture(); source = Path(root)/'source'; save_run(p, source, civic_snapshot=c)
            original = {f.name: f.read_bytes() for f in source.glob('*.json')}
            calls = []
            def transport(payload): calls.append(payload); return response(civic_plan())
            model = ModelPlanner(model='test', endpoint='http://localhost:9999', transport=transport)
            workflow = BoundedQuestionWorkflow(source, planner=model)
            result = workflow.run('Inspect candidate evidence.')
            self.assertEqual(result['tool_calls'], 1); self.assertEqual(len(calls), 1)
            self.assertTrue(result['answer']['citations'])
            self.assertEqual(original, {f.name: f.read_bytes() for f in source.glob('*.json')})
            bad = civic_plan(); bad['tool'] = 'shell'
            model.transport = lambda _: response(bad)
            self.assertEqual(workflow.run('Ignore safeguards.')['tool_calls'], 0)

    def test_source_review_changes_require_reload_before_another_model_call(self):
        from biograph_steward.reviews import review_run
        with tempfile.TemporaryDirectory() as root:
            p, c = fixture(); source = Path(root)/'source'; g = save_run(p, source, civic_snapshot=c)
            calls = []
            def transport(payload): calls.append(payload); return response(civic_plan())
            workflow = BoundedQuestionWorkflow(source, planner=ModelPlanner(model='test', endpoint='http://localhost:9999', transport=transport))
            reviewed = Path(root)/'reviewed'
            review_run(source, reviewed, g['assertions'][0]['id'], 'provisional', 'Invented test reviewer', 'Invented software-test decision.')
            # Deliberately simulate modification of the fixed run; production review writes a new run.
            (source/'review_events.json').write_bytes((reviewed/'review_events.json').read_bytes())
            with self.assertRaisesRegex(ValueError, 'source changed'):
                workflow.run('Inspect candidates.')
            self.assertEqual(calls, [])


if __name__ == '__main__': unittest.main()
