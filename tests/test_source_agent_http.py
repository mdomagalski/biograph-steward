"""Source-agent HTTP/storage contracts using invented data and injected clients."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward import source_agent
from biograph_steward.client import canonical, digest
from biograph_steward.source_agent_jobs import _header, save_source_agent_job, read_source_agent_job
from biograph_steward.webapp import create_server
import test_string_physical_source as source_fixture


class InjectedClient:
    """The controller still executes and verifies real tools on invented sources."""
    kind = 'injected_test_model'
    model = 'invented-model'
    provider = 'nim'
    max_output_tokens = 1200

    def generate(self, prompt, schema, policy, audit=None):
        data = json.loads(prompt.split('\nUntrusted input data:\n', 1)[1])
        phase = data['phase']
        if phase == 'plan':
            scope = data['request_scope']
            output = {'action': 'query', 'tool': 'native_physical',
                'arguments': {'protein_id': scope['protein_ids'][0], 'view': scope['view'],
                    'max_results': scope['constraints']['max_results'], 'max_paths': scope['constraints']['max_paths']},
                'reason': 'Inspect exact saved physical source records.'}
        elif phase == 'inspection_priority':
            output = {'action': 'inspect_sources', 'citation_ids': [data['query']['citations'][0]['id']]}
        else:
            cid = data['inspection_results'][0]['citation_id']
            option = next(row for row in data['allowed_review_options'][cid] if row['decision'] == 'abstain')
            output = {'action': 'propose', 'proposals': [{'citation_id': cid,
                'decision': option['decision'], 'reason_code': option['reason_code']}]}
        return {'status': 'completed', 'model_calls': 1, 'provider_kind': self.kind, 'output': output}


class SourceAgentJobMetadataTests(unittest.TestCase):
    def test_real_transport_requires_a_positive_integer_actual_call_count(self):
        result = {'source_run': 'invented', 'status': 'model_error',
                  'trace': {'provider_kind': 'live_nim', 'model_calls': 0, 'tool_calls': []}}
        for count in (0, None, False, True, '1'):
            result['trace']['model_calls'] = count
            self.assertFalse(_header(result)['actual_model_run'])
        result['trace']['model_calls'] = 1
        self.assertTrue(_header(result)['actual_model_run'], 'A recorded real timeout after one request is still an actual attempt.')
        result['trace']['provider_kind'] = 'injected_test_model'
        self.assertFalse(_header(result)['actual_model_run'])


class SourceAgentHttpTests(unittest.TestCase):
    def setUp(self):
        fixture = source_fixture.NativePhysicalTests()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.baseline, self.source, _, self.graph = fixture.workspace()
        self.before = {p.relative_to(self.source).as_posix(): p.read_bytes()
                       for p in self.source.rglob('*') if p.is_file()}
        self.opener = build_opener(ProxyHandler({}))
        self.start()

    def start(self, *, saved=False):
        self.server = create_server(0, self.root, saved_data_only=saved)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.worker.join()

    def tearDown(self):
        self.stop()

    def request(self, route, body=None):
        headers = {'Content-Type': 'application/json'} if body is not None else {}
        return self.opener.open(Request(self.url + route,
            json.dumps(body).encode() if body is not None else None, headers))

    def read(self, route, body=None):
        with self.request(route, body) as response:
            return json.loads(response.read())

    def run_job(self, **changes):
        body = {'run_id': self.source.name, 'question': 'Inspect candidate native physical partners for UniProtKB:P04637.'}
        body.update(changes)
        with patch.object(source_agent, 'configured_source_agent_client', return_value=InjectedClient()):
            return self.read('/api/source-agent/run', body)

    def test_configuration_is_unprobed_secret_free_and_tool_specific(self):
        with patch.object(source_agent, 'configured_source_agent_client', return_value=InjectedClient()):
            status = self.read('/api/source-agent/status?run_id=' + self.source.name)
        self.assertTrue(status['configured']); self.assertTrue(status['enabled'])
        self.assertEqual(status['availability'], 'not_probed')
        self.assertNotIn('endpoint', status); self.assertNotIn('api_key', status)
        self.assertEqual([t['name'] for t in status['catalogue']['tools']], ['native_physical'])
        with patch.object(source_agent, 'configured_source_agent_client', side_effect=ValueError('No configured model')):
            unavailable = self.read('/api/source-agent/status?run_id=' + self.source.name)
        self.assertFalse(unavailable['enabled']); self.assertFalse(unavailable['configured'])

    def test_operator_records_exact_tools_and_replays_without_a_model_or_source_write(self):
        job = self.run_job()
        self.assertEqual(job['result']['status'], 'completed')
        self.assertEqual(job['model_calls'], 3); self.assertEqual(job['tool_calls'], 2)
        self.assertEqual(job['provider_kind'], 'injected_test_model'); self.assertFalse(job['actual_model_run'])
        self.assertTrue(job['result']['answer']['citations'])
        self.assertTrue(job['result']['inspections'][0]['passport']['source_records'])
        self.assertTrue(job['progress_id'].startswith('.source_agent_progress_'))
        self.assertNotIn('/', job['progress_id'])
        events = [json.loads(p.read_text()) for p in sorted((self.root / job['progress_id']).glob('event_*.json'))]
        self.assertEqual(events[0]['event'], 'job_request')
        self.assertTrue(any(row['event'] == 'request_intent' for row in events))
        self.assertTrue(any(row['event'] == 'model_response' for row in events))
        with patch.object(source_agent, 'configured_source_agent_client', side_effect=AssertionError('No inference on replay')):
            replay = self.read('/api/source-agent/job/' + job['job_id'])
            listing = self.read('/api/source-agent/jobs?run_id=' + self.source.name)
            download = self.read('/api/source-agent/job/' + job['job_id'] + '/download')
        self.assertEqual(replay, job); self.assertEqual(download, job)
        self.assertEqual(listing['jobs'][0]['job_id'], job['job_id'])
        self.assertFalse(listing['jobs'][0]['actual_model_run'])
        self.assertEqual(self.before, {p.relative_to(self.source).as_posix(): p.read_bytes()
                                      for p in self.source.rglob('*') if p.is_file()})
        with self.assertRaises(FileExistsError):
            save_source_agent_job(job['result'], self.root, job_id=job['job_id'])

    def test_saved_review_replays_but_rejects_live_before_model_factory_and_json_parse(self):
        job = self.run_job()
        self.stop(); self.start(saved=True)
        progress_before = set(self.root.glob('.source_agent_progress_*'))
        with patch.object(source_agent, 'configured_source_agent_client', side_effect=AssertionError('No model factory')) as factory, \
                patch.object(source_agent, 'run_source_agent', side_effect=AssertionError('No model controller')) as runner:
            status = self.read('/api/source-agent/status?run_id=' + self.source.name)
            self.assertTrue(status['saved_data_only']); self.assertIsNone(status['configured']); self.assertFalse(status['enabled'])
            self.assertEqual(self.read('/api/source-agent/job/' + job['job_id']), job)
            bad = Request(self.url + '/api/source-agent/run', b'not-json', {'Content-Type': 'text/plain'})
            with self.assertRaises(HTTPError) as failure:
                self.opener.open(bad)
            self.assertEqual(failure.exception.code, 403); failure.exception.close()
            self.assertEqual((factory.call_count, runner.call_count), (0, 0))
        self.assertEqual(progress_before, set(self.root.glob('.source_agent_progress_*')))

    def test_an_interrupted_controller_keeps_immediate_events_without_publishing_a_success(self):
        with patch.object(source_agent, 'run_source_agent', side_effect=OSError('Interrupted controller')):
            with self.assertRaises(HTTPError) as failure:
                self.read('/api/source-agent/run', {'run_id': self.source.name,
                    'question': 'Inspect candidate native physical partners for UniProtKB:P04637.'})
        self.assertEqual(failure.exception.code, 400); failure.exception.close()
        progress = list(self.root.glob('.source_agent_progress_*'))
        self.assertEqual(len(progress), 1)
        self.assertEqual(json.loads((progress[0] / 'event_0001.json').read_text())['event'], 'job_request')
        self.assertEqual(list(self.root.glob('source_agent_*')), [])

    def test_record_tampering_and_changed_current_source_are_unavailable(self):
        job = self.run_job()
        folder = self.root / job['job_id']
        result = deepcopy(job['result']); result['answer']['overview'] = 'invented replacement conclusion'
        result['content_sha256'] = digest({k: v for k, v in result.items() if k != 'content_sha256'})
        raw = (canonical(result) + '\n').encode()
        manifest = json.loads((folder / 'manifest.json').read_text())
        manifest['result_sha256'] = hashlib.sha256(raw).hexdigest()
        manifest['content_sha256'] = digest({k: v for k, v in manifest.items() if k != 'content_sha256'})
        (folder / 'result.json').write_bytes(raw); (folder / 'manifest.json').write_text(canonical(manifest))
        with self.assertRaisesRegex(ValueError, 'source replay'):
            read_source_agent_job(folder, self.root)
        unavailable = self.read('/api/source-agent/jobs?run_id=' + self.source.name)
        self.assertEqual(unavailable['jobs'], []); self.assertEqual(len(unavailable['unavailable_jobs']), 1)
        (self.source / 'graph.json').write_text('{}')
        with self.assertRaises(HTTPError) as failure:
            self.read('/api/source-agent/job/' + job['job_id'])
        self.assertEqual(failure.exception.code, 400); failure.exception.close()

    def test_scope_rejection_and_model_unavailable_are_retained_as_failed_attempts(self):
        with patch.object(source_agent, 'configured_source_agent_client', side_effect=AssertionError('Scope rejected before client')):
            rejected = self.read('/api/source-agent/run', {'run_id': self.source.name,
                'question': 'Find direct binding partners for UniProtKB:P04637.'})
        self.assertEqual(rejected['result']['status'], 'scope_rejected')
        self.assertEqual(rejected['model_calls'], 0); self.assertFalse(rejected['actual_model_run'])
        with patch.object(source_agent, 'configured_source_agent_client', side_effect=ValueError('Model unavailable')):
            failed = self.read('/api/source-agent/run', {'run_id': self.source.name,
                'question': 'Inspect candidate native physical partners for UniProtKB:P04637.'})
        self.assertEqual(failed['result']['status'], 'model_unavailable')
        self.assertEqual(len(self.read('/api/source-agent/jobs?run_id=' + self.source.name)['jobs']), 2)

    def test_invalid_fields_paths_and_duplicate_query_options_are_rejected(self):
        for body in ({'run_id': '../outside', 'question': 'q'},
                     {'run_id': self.source.name, 'question': 'q', 'apply': True},
                     {'run_id': self.source.name, 'question': 'q', 'constraints': []}):
            with self.subTest(body=body), self.assertRaises(HTTPError) as failure:
                self.read('/api/source-agent/run', body)
            self.assertEqual(failure.exception.code, 400); failure.exception.close()
        with self.assertRaises(HTTPError) as failure:
            self.read('/api/source-agent/status?run_id=physical&run_id=original')
        self.assertEqual(failure.exception.code, 400); failure.exception.close()


if __name__ == '__main__':
    unittest.main()
