"""Actual saved-data graph/answer/passport/export reuse on invented native files."""
from io import BytesIO
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from zipfile import ZipFile

from biograph_steward import reviews, saved_run_cache
from biograph_steward.questions import answer_question, save_answer
from biograph_steward.webapp import create_server
import test_string_physical_source as source_fixture
from test_saved_run_cache import clear_cache


class SavedRunCacheHttpTests(unittest.TestCase):
    def setUp(self):
        fixture = source_fixture.NativePhysicalTests()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.baseline, self.run, _, self.graph = fixture.workspace()
        self.answers = {}
        for view in ('candidates', 'accepted'):
            answer = answer_question(self.graph, 'P04637', template='native_string_physical.v1',
                relations=['interactions'], view=view, source_run=self.run.name)
            identifier = 'cache_' + view
            save_answer(answer, self.root / identifier)
            self.answers[identifier] = answer
        self.before = {p.relative_to(self.run).as_posix(): p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        clear_cache(); self.addCleanup(clear_cache)
        self.server = create_server(0, self.root, access_token='invented-cache-test-token', saved_data_only=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def request(self, path, body=None):
        headers = {'Authorization': 'Bearer invented-cache-test-token'}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        return self.opener.open(Request(self.url + path,
            json.dumps(body).encode() if body is not None else None, headers))

    def json(self, path, body=None):
        with self.request(path, body) as response:
            return json.loads(response.read())

    def test_graph_saved_answers_full_passport_and_exports_share_one_verified_replay(self):
        reader = reviews.read_run
        selected = next(a['id'] for a in self.graph['assertions'] if a.get('extension_source_kind') == 'string_physical')
        with patch.object(reviews, 'read_run', wraps=reader) as calls, \
                patch('biograph_steward.webapp.PharosClient', side_effect=AssertionError('No retrieval')) as pharos, \
                patch('biograph_steward.planning.configured_planner', side_effect=AssertionError('No model')) as model, \
                patch('biograph_steward.physical_ranking.collect_ranking', side_effect=AssertionError('No live STRING')) as ranking:
            self.assertEqual(self.json('/api/run/' + self.run.name)['graph'], self.graph)
            for identifier, expected in self.answers.items():
                self.assertEqual(self.json('/api/question/' + identifier)['answer'], expected)
            passport = self.json('/api/inspect-source', {'run_id': self.run.name, 'selection_id': selected})
            self.assertEqual(passport['selection']['id'], selected)
            with self.request('/api/download/' + self.run.name) as response:
                with ZipFile(BytesIO(response.read())) as archive:
                    saved = next(name for name in archive.namelist() if name.endswith('/graph.json') and name.count('/') == 1)
                    self.assertEqual(json.loads(archive.read(saved)), self.graph)
            with self.request('/api/download/cache_candidates') as response:
                with ZipFile(BytesIO(response.read())) as archive:
                    saved = next(name for name in archive.namelist() if name.endswith('/question.json'))
                    self.assertEqual(json.loads(archive.read(saved)), self.answers['cache_candidates'])
            with self.assertRaises(HTTPError) as denied:
                self.request('/api/question', {'run_id': self.run.name, 'protein': 'P04637', 'ranking': 'physical'})
            self.assertEqual(denied.exception.code, 403); denied.exception.close()
            self.assertEqual(calls.call_count, 1)
            self.assertEqual((pharos.call_count, model.call_count, ranking.call_count), (0, 0, 0))
        self.assertEqual(self.before, {p.relative_to(self.run).as_posix(): p.read_bytes() for p in self.run.rglob('*') if p.is_file()})
        self.assertEqual(self.answers['cache_accepted']['returned_proteins'], 0)

    def test_warm_source_tamper_is_rejected_by_graph_saved_answer_and_inspection(self):
        self.json('/api/run/' + self.run.name)
        (self.run / 'graph.json').write_text('{}')
        selected = next(a['id'] for a in self.graph['assertions'] if a.get('extension_source_kind') == 'string_physical')
        for path, body in (('/api/run/' + self.run.name, None), ('/api/question/cache_candidates', None),
                           ('/api/inspect-source', {'run_id': self.run.name, 'selection_id': selected})):
            with self.subTest(path=path), self.assertRaises(HTTPError) as failure:
                self.request(path, body)
            self.assertEqual(failure.exception.code, 400); failure.exception.close()
        self.assertEqual(saved_run_cache._cached_full_read.cache_info().currsize, 0)


if __name__ == '__main__':
    unittest.main()
