"""Authenticated optional GO source inspection; invented local packets only."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward.client import digest
from biograph_steward.go_context_inspection import inspect_go_selection
from biograph_steward.webapp import create_server


class NativeGoContextHttpTests(unittest.TestCase):
    def setUp(self):
        # Reuse the existing complete invented GAF/source fixture without
        # collecting its TestCase a second time in this module.
        from test_go_context_inspection import NativeContextInspectionTests
        from test_go_context_qc import make_qc
        self.fixture = NativeContextInspectionTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root, self.graph, self.context = self.fixture.root, self.fixture.graph, self.fixture.context
        self.selected = next(row for row in self.graph['edges'] if row['record_kind'] == 'go_annotation')
        report = json.loads((self.context/'go_context_qualification.json').read_text())
        self.qc = self.root/'quality'
        make_qc(self.qc, report, self.fixture.native, unsatisfiable={self.fixture.native[1]['id']})
        self.token = 'invented-native-go-context-token'
        self.env = patch.dict(os.environ, {key: '' for key in ('BIOGRAPH_GO_CONTEXT_DIR', 'BIOGRAPH_GO_QC_DIR')})
        self.env.start(); self.addCleanup(self.env.stop)
        self.start(self.context, self.qc); self.addCleanup(self.stop)
        self.before = self.inventory()

    def start(self, context=None, qc=None):
        self.server = create_server(0, self.root, access_token=self.token,
                                   go_context_dir=context, go_qc_dir=qc)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def inventory(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def request(self, route='/api/native-go-context', body=None, *, auth=True, origin=None):
        headers = {'Content-Type': 'application/json'}
        if auth: headers['Authorization'] = 'Bearer '+self.token
        if origin: headers['Origin'] = origin
        body = body if body is not None else {'run_id': 'run', 'selection_id': self.selected['assertion_id']}
        with self.opener.open(Request(self.url+route, json.dumps(body).encode(), headers)) as response:
            return json.loads(response.read())

    def test_native_and_qc_context_preserves_not_forms_refs_and_exact_source(self):
        with patch('biograph_steward.client.PharosClient._http', side_effect=AssertionError('No retrieval')):
            result = self.request()
        self.assertEqual(result['format'], 'biograph-steward.native-go-selection.v1')
        self.assertEqual(result['source_run'], 'run')
        self.assertEqual(result['selection_id'], self.selected['assertion_id'])
        self.assertEqual(result['query'], {'protein': self.selected['subject'], 'go_id': self.selected['object']})
        self.assertEqual(result['snapshot_sha256'], self.graph['snapshot_sha256'])
        self.assertEqual(result['record_count'], 2)
        self.assertEqual(result['counts'], {'positive_records': 1, 'not_records': 1})
        self.assertEqual(result['records'][0]['raw_line'], self.fixture.native[0]['raw_line'])
        self.assertEqual(result['records'][0]['reference_identifiers'], ['PMID:36949045', 'OTHER:one'])
        self.assertTrue(result['records'][0]['negated'])
        self.assertTrue(result['records'][1]['saved_quality_control']['extension_unsatisfiable'])
        self.assertEqual(result['records'][1]['saved_quality_control']['taxon_result']['result_type'], 'PASS')
        self.assertFalse(result['historical_record_identity_established'])
        self.assertFalse(result['original_qualifiers_backfilled'])
        self.assertFalse(result['GO_rules_or_reasoner_reexecuted'])
        self.assertFalse(result['optional_native_parser_reexecuted'])
        self.assertFalse(result['independent_biological_accuracy_established'])
        self.assertEqual(result['quality_control']['status'], 'verified_saved_output')
        self.assertEqual(result['content_sha256'], digest({k:v for k,v in result.items() if k != 'content_sha256'}))
        self.assertEqual(self.inventory(), self.before)

    def test_source_guide_offer_is_optional_and_only_for_go_assertions(self):
        result = self.request('/api/inspect-source')
        self.assertEqual(result['native_go_context'], {'configured': True, 'eligible': True})
        non_go = next(row for row in self.graph['assertions'] if row['kind'] != 'go_annotation')
        result = self.request('/api/inspect-source', {'run_id': 'run', 'selection_id': non_go['id']})
        self.assertEqual(result['native_go_context'], {'configured': True, 'eligible': False})
        self.stop(); self.start()
        result = self.request('/api/inspect-source')
        self.assertNotIn('native_go_context', result)
        with self.assertRaises(HTTPError) as error: self.request()
        self.assertEqual(error.exception.code, 503); error.exception.close()

    def test_auth_origin_exact_options_and_non_go_selection_fail_closed(self):
        with self.assertRaises(HTTPError) as error: self.request(auth=False)
        self.assertEqual(error.exception.code, 401); error.exception.close()
        with self.assertRaises(HTTPError) as error: self.request(origin='https://unrelated.invalid')
        self.assertEqual(error.exception.code, 403); error.exception.close()
        non_go = next(row for row in self.graph['assertions'] if row['kind'] != 'go_annotation')
        for body in ({'run_id': '../run', 'selection_id': self.selected['id']},
                     {'run_id': 'run', 'selection_id': non_go['id']},
                     {'run_id': 'run', 'selection_id': self.selected['id'], 'context': '/etc'},
                     {'run_id': 'run', 'selection_id': 'missing'}):
            with self.subTest(body=body), self.assertRaises(HTTPError) as error: self.request(body=body)
            self.assertEqual(error.exception.code, 400); error.exception.close()

    def test_invalid_configured_context_or_qc_never_falls_back_to_unqualified_rows(self):
        path = self.context/'native_records.jsonl'; original = path.read_bytes()
        path.write_bytes(original+b'\n')
        with self.assertRaises(HTTPError) as error: self.request()
        self.assertEqual(error.exception.code, 400); error.exception.close()
        path.write_bytes(original)
        path = self.qc/'official_rule_calls.jsonl'; path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(HTTPError) as error: self.request()
        self.assertEqual(error.exception.code, 400); error.exception.close()

    def test_optional_qc_does_not_masquerade_as_a_pass(self):
        self.stop(); self.start(self.context)
        # The GAF contains another GO term but inspection stays on the exact
        # selected pair. All its competing rows remain available.
        result = self.request()
        self.assertEqual(result['quality_control']['status'], 'not_configured')
        self.assertFalse(any('saved_quality_control' in row for row in result['records']))
        self.assertEqual(result['record_count'], 2)
        self.assertFalse(result['biological_absence_inferred'])

    def test_qualified_binding_uses_preserved_baseline_not_retained_hash(self):
        graph = deepcopy(self.graph)
        report = json.loads((self.context/'go_context_qualification.json').read_text())
        graph['qualified_view'] = {'packet_id': report['packet_id']}
        folder = self.root/'qualified'
        baseline = folder/'source_retained_package/baseline_packet/source/graph.json'
        baseline.parent.mkdir(parents=True)
        baseline.write_bytes((self.fixture.packet/'source/graph.json').read_bytes())
        result = inspect_go_selection(self.context, graph, self.selected['id'],
            source_run='qualified', source_folder=folder)
        self.assertEqual(result['record_count'], 2)
        baseline.write_bytes(baseline.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError, 'baseline source bytes'):
            inspect_go_selection(self.context, graph, self.selected['id'],
                source_run='qualified', source_folder=folder)


if __name__ == '__main__':
    unittest.main()
