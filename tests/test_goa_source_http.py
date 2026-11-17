"""Serve only replayed native GOA publication bytes, including retained views.

The small invented packet uses the actual source adapter, Gold package, retained
workspace and HTTP handlers. Source readers are not patched at the HTTP boundary.
"""
import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward import evidence_extension, gold_packet, qualified_workspace
from biograph_steward.inspection import _source_path
from biograph_steward.reviews import read_run
from biograph_steward.webapp import create_server
import test_goa_source as source_fixture


class NativeGoSourceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = source_fixture.GoaSourceTests(methodName='test_complete_source_replay_preserves_every_native_field_and_new_source_identity')
        cls.engine.setUp()
        cls.addClassCleanup(cls.engine.doCleanups)
        cls.root = cls.engine.root
        cls.engine.publish()
        cls.normal = cls.root / 'normal'
        evidence_extension.publish_extension(cls.engine.run, {'goa': cls.engine.publication}, cls.normal)
        packet, retained = cls.root / 'extended_packet', cls.root / 'extended_retained'
        gold_packet.export_packet(cls.normal, packet)
        gold_packet.save_decisions(packet, packet / 'decisions.template.json', retained)
        cls.qualified = cls.root / 'qualified'
        qualified_workspace.publish_workspace(retained, cls.qualified)
        cls.native_assertion = next(a['id'] for a in read_run(cls.normal)[2]['assertions']
                                    if a['kind'] == 'native_go_annotation')
        cls.relative = 'source/census/qualified_recoveries.gaf'
        cls.expected = (cls.engine.publication / cls.relative).read_bytes()

    def setUp(self):
        self.token = 'invented-native-go-source-token'
        self.server = create_server(0, self.root, access_token=self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, run, relative=None, *, auth=True, kind='goa'):
        path = '/api/extension-source/' + run + '/extension_sources/' + kind + '/' + (relative or self.relative)
        headers = {'Authorization': 'Bearer ' + self.token} if auth else {}
        return self.opener.open(Request(self.url + path, headers=headers))

    def passport(self, run):
        value = {'run_id': run, 'selection_id': self.native_assertion}
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.token}
        with self.opener.open(Request(self.url + '/api/inspect-source', json.dumps(value).encode(), headers)) as response:
            return json.loads(response.read())

    def error(self, code, run, relative=None, **options):
        with self.assertRaises(HTTPError) as caught:
            self.get(run, relative, **options)
        self.assertEqual(caught.exception.code, code)
        caught.exception.close()

    def test_ordinary_native_publication_download_is_exact_and_authenticated(self):
        self.error(401, 'normal', auth=False)
        with self.get('normal') as response:
            self.assertEqual(response.read(), self.expected)
            self.assertIn('attachment;', response.headers['Content-Disposition'])

    def test_qualified_download_replays_its_nested_ordinary_source(self):
        # The source publication exists only inside the preserved Gold packet.
        self.assertFalse((self.qualified / 'evidence_extension.json').exists())
        self.assertTrue((self.qualified / qualified_workspace.PACKAGE /
                         'baseline_packet/source/evidence_extension.json').is_file())
        self.assertTrue(read_run(self.qualified)[2]['qualified_view']['read_only'])
        with self.get('qualified') as response:
            self.assertEqual(response.read(), self.expected)

    def test_manifest_scope_path_and_source_kind_are_not_expanded(self):
        for run in ('normal', 'qualified'):
            with self.subTest(run=run):
                self.error(400, run, 'source/not-published.txt')
                self.error(400, run, '../snapshot.json')
                self.error(404, run, kind='unregistered')
        self.assertIsNone(_source_path('normal', 'extension_sources/goa/../snapshot.json'))
        self.assertIsNone(_source_path('normal', 'extension_sources/unregistered/source/file.json'))

    def test_native_passport_preserves_fields_and_links_for_both_workspace_types(self):
        for run in ('normal', 'qualified'):
            with self.subTest(run=run):
                result = self.passport(run)
                native = [s for s in result['sections'] if s['title'] == 'Recorded native GO annotation']
                self.assertEqual(len(native), 2)
                self.assertEqual({s['fields']['relation_literal'] for s in native}, {'involved_in'})
                self.assertTrue(all(len(s['fields']['raw_fields']) == 17 for s in native))
                self.assertTrue(all(s['fields']['source_gaf_sha256'] == self.engine.gaf_pin for s in native))
                links = [link for link in result['links'] if link['kind'] == 'local_source']
                self.assertTrue(links)
                for link in links:
                    self.assertTrue(link['url'].startswith('/api/extension-source/' + run + '/extension_sources/goa/'))
                    with self.opener.open(Request(self.url + link['url'].split('#', 1)[0],
                            headers={'Authorization': 'Bearer ' + self.token})) as response:
                        self.assertTrue(response.read())
                self.assertFalse(any('construct' in s['title'].lower() for s in result['sections']))

    def test_changed_nested_publication_is_not_returned(self):
        path = (self.qualified / qualified_workspace.PACKAGE /
                'baseline_packet/source/extension_sources/goa' / self.relative)
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'!unrecorded change\n')
            self.error(400, 'qualified')
        finally:
            path.write_bytes(original)
        with self.get('qualified') as response:
            self.assertEqual(response.read(), original)


if __name__ == '__main__':
    unittest.main()
