"""Qualified source views may use the existing read-only Neptune inspector."""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from biograph_steward.reviews import read_run
from biograph_steward.webapp import create_server
from test_neptune_http import FakeMirror
import test_qualified_workspace as source_fixture


class QualifiedNeptuneHttpTests(unittest.TestCase):
    def setUp(self):
        source_fixture.QualifiedWorkspaceTests.setUp(self)
        self.mirror = FakeMirror()
        self.server = create_server(0, self.root, neptune_mirror=self.mirror)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def inspect(self):
        body = {'run_id': 'qualified', 'node_id': self.protein, 'limit': 20}
        request = Request(self.url + '/api/neptune-inspect', json.dumps(body).encode(),
                          {'Content-Type': 'application/json'})
        with self.opener.open(request) as response:
            return json.load(response)

    def test_neptune_receives_retained_graph_and_leaves_source_unchanged(self):
        before = sha(self.out / 'graph.json')
        retained = read_run(self.out)[2]
        result = self.inspect()
        self.assertEqual(result['backend'], 'neptune')
        self.assertTrue(result['read_only'])
        self.assertEqual(result['graph_sha256'], digest(retained))
        self.assertEqual(self.mirror.calls[0][0], retained)
        self.assertEqual(len(retained['edges']), len(self.baseline['edges']) - 1)
        self.assertEqual(sha(self.out / 'graph.json'), before)

    def test_changed_qualified_source_is_rejected_before_cloud_read(self):
        (self.out / 'graph.json').write_text('{}')
        with self.assertRaises(HTTPError) as error:
            self.inspect()
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        self.assertEqual(self.mirror.calls, [])


if __name__ == '__main__':
    unittest.main()
