"""Synthetic metadata/source capture checks; no reference outcomes are read."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import PharosClient, digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import load_packet
from tools.coessentiality_feasibility import transfer_source as module
from test_pharos_inventory import InventoryAPI


class TransferSourceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.sample = self.root / 'sample'
        self.sample.mkdir()
        self.selected = [{'ncbi_gene_id': '1', 'accession': 'P04637', 'subject': 'UniProtKB:P04637'},
                         {'ncbi_gene_id': '2', 'accession': 'P00533', 'subject': 'UniProtKB:P00533'}]
        self.sample_report = {'content_sha256': 'a' * 64, 'test_only': True}
        write_json(self.sample / 'report.json', self.sample_report)
        # The sampler's own SRS/registry replay has separate tests. This seam
        # supplies invented metadata while exercising real capture/replay/Gold.
        sampler = patch.object(module, 'sample_frame', return_value=(self.sample_report, {}, self.selected))
        sampler.start()
        self.addCleanup(sampler.stop)
        self.api = InventoryAPI()
        self.api.context['P04637']['pathways'][0].update(type='WikiPathways', sourceID='WP1_r10',
            url='http://www.wikipathways.org/instance/WP1_r10')
        capability = {'format': 'invented-test-only-capability', 'all_required_capabilities_present': True,
            'sample_IDs_queried': False, 'outcome_data_opened': False, 'version_after': 'TEST-ONLY',
            'version_before': 'TEST-ONLY',
            'endpoint': 'https://pharos-api.ncats.io/graphql'}
        capability['content_sha256'] = digest(capability)
        self.capability = self.root / 'capability.json'
        write_json(self.capability, capability)

    def capture(self, name='capture', **kwargs):
        return module.capture(self.sample, self.sample_report['content_sha256'], self.root / name,
            capability_report=self.capability, capability_file_sha256=sha(self.capability),
            client_factory=lambda: PharosClient(transport=self.api), **kwargs)

    def test_pathways_only_real_ordinary_gold_preserves_zero_context_and_source_locators(self):
        result = self.capture(chunk_size=1)
        self.assertTrue(result['source_ready_for_comparison'])
        self.assertEqual(result['sample_gene_count'], 2)
        self.assertEqual(result['complete_zero_Wiki_context_genes'], 1)
        self.assertEqual(result['observed_WikiPathways_rows_from_complete_source'], 1)
        self.assertFalse(result['outcome_values_opened'])
        self.assertFalse(result['other_families_retrieved'])
        report, selected, ledger = module.verify_capture(self.root / 'capture', result['content_sha256'])
        self.assertEqual(report, result)
        self.assertEqual(selected, self.selected)
        self.assertTrue(ledger[1]['complete_zero_Wiki_context'])
        _, graph = load_packet(self.root / 'capture/source_packet')
        self.assertEqual({t['id'] for t in graph['targets']}, {r['subject'] for r in self.selected})
        self.assertEqual({e['record_kind'] for e in graph['edges']}, {'pathway_membership'})
        self.assertTrue(all(e['retrieval_provenance']['source_responses'] for e in graph['edges']))
        snapshot = json.loads((self.root / 'capture/ordinary_run/snapshot.json').read_text())
        self.assertEqual(snapshot['data_kind'], 'synthetic_demo')
        self.assertTrue(all(row['status'] == 'not_requested' for row in snapshot['retrieval']['context']['targets']
                            if row['family'] != 'pathways'))
        calls = [c['query'] for c in self.api.calls]
        self.assertFalse(any('Scoped_' in q and 'Scoped_pathways' not in q for q in calls))
        self.assertFalse(any('DiseaseTargets' in q or 'associatedDisease' in q for q in calls))

    def test_any_missing_identity_keeps_full_frame_unknown_and_exports_no_graph(self):
        self.api.identities['P00533'] = None
        result = self.capture()
        self.assertFalse(result['source_ready_for_comparison'])
        self.assertEqual(result['whole_comparison_status'], 'UNKNOWN_REQUIRED_SOURCE')
        self.assertEqual(result['sample_gene_count'], 2)
        self.assertEqual(result['unknown_required_source_genes'], 1)
        _, _, ledger = module.verify_capture(self.root / 'capture', result['content_sha256'])
        self.assertEqual(len(ledger), 2)
        self.assertEqual(ledger[1]['identity_status'], 'not_found')
        self.assertIsNone(ledger[1]['WikiPathways_rows'])
        self.assertFalse(ledger[1]['complete_zero_Wiki_context'])
        self.assertFalse((self.root / 'capture/source_packet').exists())

    def test_inconsistent_counts_and_actual5000cap_are_not_zero_or_complete(self):
        self.api.modify = lambda family, uid, skip, response: {**response,
            'reported': [{'name': 'TEST', 'value': len(self.api.context[uid]['pathways']) + 1}]}
        result = self.capture('inconsistent')
        self.assertFalse(result['source_ready_for_comparison'])
        ledger = json.loads((self.root / 'inconsistent/source_coverage.json').read_text())
        self.assertEqual(ledger[0]['pathway_coverage_status'], 'inconsistent')
        self.assertIsNone(ledger[0]['WikiPathways_rows'])
        self.api.modify = lambda family, uid, skip, response: response
        self.api.context['P04637']['pathways'] = [{'pwid': i, 'name': 'Invented', 'type': 'WikiPathways',
            'sourceID': 'WP1_r10', 'url': 'http://www.wikipathways.org/instance/WP1_r10'} for i in range(5001)]
        result = self.capture('capped')
        self.assertFalse(result['source_ready_for_comparison'])
        ledger = json.loads((self.root / 'capped/source_coverage.json').read_text())
        self.assertEqual(ledger[0]['pathway_coverage_status'], 'capped')
        self.assertEqual(ledger[0]['retrieved_pathway_rows'], 5000)
        self.assertIsNone(ledger[0]['WikiPathways_rows'])

    def test_version_change_rejects_before_target_queries_and_preserves_unknown_frame(self):
        original = self.api.__call__
        versions = 0
        def changed(payload):
            nonlocal versions
            if 'DatabaseVersion' in payload['query']:
                versions += 1
                if versions > 1:
                    return {'data': {'dbVersion': 'CHANGED'}}
            return original(payload)
        with patch.object(module, 'PharosClient', wraps=PharosClient):
            result = module.capture(self.sample, self.sample_report['content_sha256'], self.root / 'changed',
                capability_report=self.capability, capability_file_sha256=sha(self.capability),
                client_factory=lambda: PharosClient(transport=changed))
        self.assertFalse(result['source_ready_for_comparison'])
        self.assertEqual(result['unknown_required_source_genes'], 2)
        self.assertFalse(any('ExplicitInventoryTargets' in row['query'] for row in self.api.calls))
        module.verify_capture(self.root / 'changed', result['content_sha256'])

    def test_resealed_chunk_projection_changes_cannot_pass_native_replay(self):
        result = self.capture()
        chunk = json.loads((self.root / 'capture/chunks/00000.json').read_text())
        chunk['targets'][0]['pathways'][0]['name'] = 'changed unbound projection'
        chunk.pop('content_sha256')
        chunk['content_sha256'] = digest(chunk)
        with self.assertRaisesRegex(ValueError, 'replay exactly'):
            module.replay_chunk(chunk, [r['accession'] for r in self.selected],
                                [r['accession'] for r in self.selected], 'TEST-ONLY')
        path = self.root / 'capture/source_coverage.json'
        path.write_text('[]')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            module.verify_capture(self.root / 'capture', result['content_sha256'])

    def reseal_report(self, directory, *, updates=None):
        directory = Path(directory)
        report = json.loads((directory / 'report.json').read_text())
        report.pop('content_sha256')
        report.update(updates or {})
        report['files'] = {p.relative_to(directory).as_posix(): sha(p)
                           for p in directory.rglob('*') if p.is_file() and p != directory / 'report.json'}
        report['content_sha256'] = digest(report)
        write_json(directory / 'report.json', report)

    def test_foreign_valid_gold_packet_cannot_replace_captured_ordinary_source(self):
        self.capture('first')
        self.api.context['P04637']['pathways'][0]['name'] = 'Different valid invented source'
        self.capture('foreign')
        foreign, _ = load_packet(self.root / 'foreign/source_packet')
        shutil.rmtree(self.root / 'first/source_packet')
        shutil.copytree(self.root / 'foreign/source_packet', self.root / 'first/source_packet')
        self.reseal_report(self.root / 'first', updates={'source_packet_id': foreign['packet_id'],
            'source_graph_file_sha256': sha(self.root / 'first/source_packet/source/graph.json')})
        with self.assertRaisesRegex(ValueError, 'Gold source packet differs'):
            module.verify_capture(self.root / 'first')

    def test_resealed_capability_and_scope_claim_changes_fail_rebinding(self):
        self.capture('capability_change')
        path = self.root / 'capability_change/capability.json'
        value = json.loads(path.read_text())
        value['endpoint'] = 'https://different.invalid/graphql'
        value.pop('content_sha256')
        value['content_sha256'] = digest(value)
        write_json(path, value)
        self.reseal_report(self.root / 'capability_change')
        with self.assertRaisesRegex(ValueError, 'copied capability'):
            module.verify_capture(self.root / 'capability_change')
        self.capture('scope_change')
        path = self.root / 'scope_change/plan.json'
        value = json.loads(path.read_text())
        value['other_families_requested'] = True
        value.pop('content_sha256')
        value['content_sha256'] = digest(value)
        write_json(path, value)
        self.reseal_report(self.root / 'scope_change', updates={'plan_content_sha256': value['content_sha256']})
        with self.assertRaisesRegex(ValueError, 'plan/profile'):
            module.verify_capture(self.root / 'scope_change')
        self.capture('status_change')
        self.reseal_report(self.root / 'status_change', updates={'whole_comparison_status': 'SCIENTIFICALLY_CONFIRMED'})
        with self.assertRaisesRegex(ValueError, 'incomplete source'):
            module.verify_capture(self.root / 'status_change')


if __name__ == '__main__':
    unittest.main()
