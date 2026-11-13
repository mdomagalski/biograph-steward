"""Actual retained-workspace HTTP query, export and immutable-source checks."""
from io import BytesIO
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from biograph_steward.webapp import create_server
from biograph_steward.file_utils import sha
import test_qualified_workspace as source_fixture


class QualifiedWorkspaceHttpTests(unittest.TestCase):
    def setUp(self):
        source_fixture.QualifiedWorkspaceTests.setUp(self)
        self.server = create_server(0, self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def post(self, path, body):
        with urlopen(Request(self.url+path, data=json.dumps(body).encode(),
                            headers={'Content-Type': 'application/json'})) as response:
            return json.loads(response.read())

    def query(self):
        return self.post('/api/question', {'run_id': 'qualified', 'protein': self.protein,
            'template': 'qualified_pathway_source_context.v1', 'relations': ['shared_pathways'],
            'view': 'candidates', 'max_paths': 5})

    def test_actual_graph_query_reopen_and_portable_group_export(self):
        before = sha(self.out/'graph.json')
        with urlopen(self.url+'/api/run/qualified') as response:
            graph = json.loads(response.read())['graph']
        self.assertEqual(len(graph['edges']), len(self.baseline['edges']) - 1)
        result = self.query()
        self.assertEqual(result['answer']['results'][0]['eligible_path_count'], 2)
        with urlopen(self.url+'/api/question/'+result['question_id']) as response:
            self.assertEqual(json.loads(response.read()), result)
        with urlopen(self.url+'/api/download/'+result['question_id']) as response:
            archive = ZipFile(BytesIO(response.read()))
            names = {name.split('/')[-1] for name in archive.namelist()}
            self.assertTrue({'question.json', 'paths.tsv', 'source_context_groups.json', 'qualified_view.json'} <= names)
        self.assertEqual(sha(self.out/'graph.json'), before)

    def test_readonly_view_cannot_be_rebuilt_or_exported_as_undecided(self):
        before = sha(self.out/'graph.json')
        for path, extra in [('/api/review', {'assertion_id': self.graph['assertions'][0]['id'],
            'state': 'accepted', 'reviewer': 'Invented', 'reason': 'Invented'}),
            ('/api/submission-export', {})]:
            with self.assertRaises(HTTPError) as caught:
                self.post(path, {'run_id': 'qualified', **extra})
            self.assertEqual(caught.exception.code, 400)
            self.assertIn('read-only', caught.exception.read().decode())
            caught.exception.close()
        self.assertEqual(sha(self.out/'graph.json'), before)

    def test_saved_question_refuses_changed_materialized_graph(self):
        result = self.query()
        (self.out/'graph.json').write_text('{}')
        for path in ('/api/question/', '/api/download/'):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.url+path+result['question_id'])
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()


if __name__ == '__main__':
    unittest.main()
