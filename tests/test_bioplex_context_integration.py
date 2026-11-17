"""Invented context-only packets exercise source, graph and HTTP boundaries."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward import bioplex_source as bp
from biograph_steward.evidence_extension import publish_extension
from biograph_steward.gold_packet import export_packet, load_packet, save_decisions, load_decisions
from biograph_steward.graph import save_run
from biograph_steward.inspection import inspect_selection
from biograph_steward.reviews import read_run
from biograph_steward.webapp import create_server, report_html
from test_assay_attachment import cohort_snapshot
from test_bioplex_source import companion, directed, raw


class BioPlexContextIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.snapshot = cohort_snapshot()
        self.base = save_run(self.snapshot, self.root / 'base')
        edge = next(e for e in self.base['edges'] if e['record_kind'] == 'protein_interaction')
        self.a, self.b = [edge[k].removeprefix('UniProtKB:') for k in ('subject', 'object')]
        self.c, self.d = self.root / 'c.tsv', self.root / 'd.tsv'
        self.c.write_bytes(raw([companion(ua=self.a, ub=self.b)], bp.COMPANION_COLUMNS))
        self.d.write_bytes(raw([directed()], bp.DIRECTED_COLUMNS))
        for key, path in [('COMPANION_SHA256', self.c), ('DIRECTED_SHA256', self.d)]:
            p = patch.object(bp, key, hashlib.sha256(path.read_bytes()).hexdigest())
            p.start(); self.addCleanup(p.stop)
        bp.publish_release(self.c, self.d, self.snapshot, self.root / 'publication')
        self.run = self.root / 'context'
        self.graph = publish_extension(self.root / 'base', {'bioplex': self.root / 'publication'}, self.run)

    def test_context_does_not_strengthen_graph_and_survives_complete_export(self):
        for key in ('nodes', 'edges', 'assertions', 'targets', 'review_events'):
            self.assertEqual(self.graph[key], self.base[key], key)
        checked = read_run(self.run)[2]
        self.assertEqual(checked, self.graph)
        observation = checked['extension_observations'][0]
        self.assertIsNone(observation['graph_edge_id'])
        self.assertTrue(observation['baseline_pair_edge_ids'])
        inspection = inspect_selection(checked, observation['id'], run_id='context')
        self.assertEqual(inspection['selection']['record_kind'], 'cell_line_coassociation_observation')
        self.assertIsNone(inspection['assertion'])
        self.assertEqual(inspection['review']['state'], 'not_applicable')
        self.assertIn('no assertion to accept or prune', inspection['review']['note'])
        self.assertIn('not human expert review', inspection['review']['note'])
        self.assertEqual(inspection['actions'], [])
        self.assertIn('adds no graph edge', inspection['summary'])
        self.assertIn('not direction-specific', inspection['sections'][1]['text'])
        self.assertTrue(any('/extension_sources/bioplex/' in link['url'] for link in inspection['links']))
        packet = self.root / 'packet'
        export_packet(self.run, packet); load_packet(packet)
        report = save_decisions(packet, packet / 'decisions.template.json', self.root / 'decisions')
        _, retained = load_decisions(self.root / 'decisions')
        self.assertEqual(report['counts'], {'keep': 0, 'prune': 0, 'abstain': len(self.base['edges'])})
        expected = deepcopy(checked['extension_observations'])
        for item in expected:
            item['retention'] = {'baseline_graph_edge_id': None, 'decision': None}
        self.assertEqual(retained['extension_observations'], expected)
        self.assertEqual(retained['edges'], checked['edges'])
        native = self.root / 'decisions/baseline_packet/source/extension_sources/bioplex' / bp.COMPANION_FILE
        self.assertEqual(native.read_bytes(), self.c.read_bytes())

    def test_authenticated_inspection_and_source_download_remain_read_only(self):
        server = create_server(0, self.root, access_token='invented-cell-context-token')
        server.RequestHandlerClass.log_message = lambda *args: None
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join()))
        url = 'http://127.0.0.1:' + str(server.server_port)
        opener = build_opener(ProxyHandler({}))
        path = '/api/extension-source/context/extension_sources/bioplex/' + bp.COMPANION_FILE
        with self.assertRaises(HTTPError) as caught: opener.open(url + path)
        self.assertEqual(caught.exception.code, 401); caught.exception.close()
        before = {p.relative_to(self.run).as_posix(): p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        headers = {'Authorization': 'Bearer invented-cell-context-token'}
        with ExitStack() as stack:
            for target in ('biograph_steward.client.PharosClient.execute',
                           'biograph_steward.model_transport.JSONModelClient.generate'):
                stack.enter_context(patch(target, side_effect=AssertionError('No new retrieval or model')))
            with opener.open(Request(url + path, headers=headers)) as response:
                self.assertEqual(response.read(), self.c.read_bytes())
                self.assertIn('attachment', response.headers['Content-Disposition'])
            body = {'run_id': 'context', 'selection_id': self.graph['extension_observations'][0]['id']}
            with opener.open(Request(url + '/api/inspect-source', data=json.dumps(body).encode(),
                headers={**headers, 'Content-Type': 'application/json'})) as response:
                answer = json.loads(response.read())
            self.assertEqual(answer['selection']['record_kind'], 'cell_line_coassociation_observation')
            self.assertEqual(answer['model_calls'], 0); self.assertEqual(answer['source_fetches'], 0)
        after = {p.relative_to(self.run).as_posix(): p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        html = report_html(self.graph)
        self.assertEqual(html.count('id="bioplexPanel"'), 1)
        self.assertIn('HCT116 mismatch-repair context', html)
        self.assertIn('do not establish one joint complex', html)


if __name__ == '__main__':
    unittest.main()
