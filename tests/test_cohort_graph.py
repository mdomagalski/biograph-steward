"""A declared protein cohort is not a disease association or assay reference."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import PharosClient, digest
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import build_graph, save_run, verify_snapshot
from test_normalization import fixture as context_fixture, resign
from test_retrieval import ContextAPI


def fixture():
    snapshot = context_fixture()
    ids = [row['uniprot'] for row in snapshot['targets']]
    for row in snapshot['targets']:
        row.pop('diseaseAssociationDetails', None)
    snapshot['disease'] = None
    snapshot['scope'] = {
        'kind': 'protein_cohort', 'name': 'Explicit test proteins',
        'requested_uniprot': ids + ['Q5TEC6'],
        'resolutions': [
            {'requested_uniprot': uid, 'returned_uniprot': uid, 'status': 'resolved'}
            for uid in ids
        ] + [{'requested_uniprot': 'Q5TEC6', 'returned_uniprot': None, 'status': 'not_found'}],
    }
    return resign(snapshot)


class CohortGraphTests(unittest.TestCase):
    def test_no_disease_node_or_membership_is_invented(self):
        graph = build_graph(fixture())
        self.assertIsNone(graph['disease'])
        self.assertIsNone(graph['disease_node_id'])
        self.assertFalse(any(node['category'] == 'biolink:Disease' for node in graph['nodes']))
        self.assertFalse(any(edge['record_kind'].startswith('disease_') for edge in graph['edges']))
        self.assertEqual(graph['summary']['unique_association_pairs'], 0)
        self.assertEqual(graph['benchmark_readiness']['status'], 'not_applicable')
        self.assertEqual(graph['benchmark_readiness']['pairs'], [])
        self.assertTrue(all(target['association_record_count'] == 0 for target in graph['targets']))

    def test_unresolved_identity_is_visible_without_a_source_protein_node(self):
        snapshot = fixture()
        before = deepcopy(snapshot)
        graph = build_graph(snapshot)
        self.assertEqual(snapshot, before)
        self.assertEqual(graph['scope'], snapshot['scope'])
        self.assertEqual(graph['unresolved_targets'], snapshot['scope']['resolutions'][-1:])
        self.assertNotIn('UniProtKB:Q5TEC6', {node['id'] for node in graph['nodes']})
        self.assertEqual(graph['summary']['requested_proteins'], len(snapshot['targets']) + 1)
        self.assertEqual(graph['summary']['resolution_statuses'], {'not_found': 1, 'resolved': len(snapshot['targets'])})

    def test_identifier_mismatch_does_not_substitute_another_protein(self):
        snapshot = fixture()
        snapshot['scope']['resolutions'][-1].update(status='identity_mismatch', returned_uniprot='P01116')
        graph = build_graph(resign(snapshot))
        self.assertEqual(graph['unresolved_targets'][0]['returned_uniprot'], 'P01116')
        self.assertNotIn('UniProtKB:P01116', {node['id'] for node in graph['nodes']})

    def test_empty_resolved_cohort_is_published_as_unresolved_not_an_error_or_negative(self):
        snapshot = fixture()
        snapshot['targets'] = []
        for row in snapshot['scope']['resolutions']:
            row.update(status='not_found', returned_uniprot=None)
        graph = build_graph(resign(snapshot))
        self.assertEqual(graph['nodes'], [])
        self.assertEqual(graph['edges'], [])
        self.assertEqual(len(graph['unresolved_targets']), len(snapshot['scope']['requested_uniprot']))
        self.assertEqual(graph['benchmark_readiness']['counts']['reviewed_negative_labels'], 0)

    def test_accidental_disease_association_data_remains_quarantined(self):
        snapshot = fixture()
        records = [{'name': 'Unexpected disease', 'source': 'TEST', 'evidence': 'TEST'}]
        snapshot['targets'][0]['diseaseAssociationDetails'] = records
        graph = build_graph(resign(snapshot))
        self.assertFalse(any(node['category'] == 'biolink:Disease' for node in graph['nodes']))
        entry = next(row for row in graph['quarantine'] if row['reason'] == 'disease_associations_outside_protein_cohort_scope')
        self.assertEqual(entry['record'], records)
        self.assertEqual(entry['locator'], 'snapshot.json#/targets/0/diseaseAssociationDetails')

    def test_source_normalization_and_claim_identity_are_reused(self):
        before = build_graph(context_fixture())
        after = build_graph(fixture())
        old = next(row for row in before['assertions'] if row['kind'] == 'protein_interaction')
        new = next(row for row in after['assertions'] if row['kind'] == 'protein_interaction')
        self.assertEqual(old['id'], new['id'])
        self.assertEqual(old['source_record_count'], new['source_record_count'])
        self.assertEqual(new['source_record_count'], 3)
        edge = next(row for row in after['edges'] if row['record_kind'] == 'protein_interaction')
        self.assertEqual(edge['predicate'], 'biograph:has_interaction_annotation')
        self.assertEqual({row['properties'][0]['value'] for row in edge['source_scores_raw']['properties_by_view']}, {'0.8', '0.9'})
        self.assertFalse(edge['biologically_validated'])
        self.assertIsNone(new['independent_evidence_count'])

    def test_context_retains_snapshot_and_response_provenance(self):
        snapshot = fixture()
        graph = build_graph(snapshot)
        for row in graph['context_records']:
            self.assertEqual(row['snapshot_sha256'], snapshot['content_sha256'])
            for location in row['source_response_locators']:
                envelope = snapshot['requests'][location['request_index']]
                value = envelope['response']
                for part in location['response_pointer'].strip('/').split('/'):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                self.assertEqual(value, row['record'])
                self.assertEqual(envelope['response_sha256'], location['response_sha256'])

    def test_all_cohort_edges_including_pathways_link_directly_to_raw_source_rows(self):
        snapshot = PharosClient(transport=ContextAPI()).build_snapshot(
            'Test disease', profile='scoped', tissue_term='colon rectum')
        ids = [row['uniprot'] for row in snapshot['targets']]
        for row in snapshot['targets']:
            row.pop('diseaseAssociationDetails', None)
        snapshot['disease'] = None
        snapshot['scope'] = {
            'kind': 'protein_cohort', 'name': 'Source provenance test',
            'requested_uniprot': ids,
            'resolutions': [{'requested_uniprot': uid, 'status': 'resolved', 'returned_uniprot': uid} for uid in ids],
        }
        graph = build_graph(resign(snapshot))
        pathways = [edge for edge in graph['edges'] if edge['record_kind'] == 'pathway_membership']
        self.assertTrue(pathways)
        for edge in graph['edges']:
            expected_rows = []
            for locator in edge['record_locators']:
                value = snapshot
                for part in locator.split('#/', 1)[1].split('/'):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                expected_rows.append(value)
            provenance = edge['retrieval_provenance']
            self.assertEqual(provenance['database_version'], snapshot['db_version'])
            self.assertTrue(provenance['source_responses'], edge['record_kind'])
            for location in provenance['source_responses']:
                envelope = snapshot['requests'][location['request_index']]
                value = envelope['response']
                for part in location['response_pointer'].strip('/').split('/'):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                self.assertIn(value, expected_rows)
                self.assertEqual(location['response_sha256'], envelope['response_sha256'])
                self.assertEqual(location['retrieved_at'], envelope['retrieved_at'])
            if edge['record_kind'] == 'pathway_membership':
                self.assertIn(edge['evidence_record'], expected_rows)

    def test_inconsistent_scope_and_resolution_are_rejected(self):
        modifications = [
            lambda s: s['scope'].update(kind='unknown'),
            lambda s: s['scope'].update(name=' '),
            lambda s: s.pop('disease'),
            lambda s: s.update(disease={'name': 'A disease'}),
            lambda s: s['scope']['requested_uniprot'].append('Q5TEC6'),
            lambda s: s['scope']['requested_uniprot'].__setitem__(0, 'UniProtKB:P04637'),
            lambda s: s['scope']['resolutions'].pop(),
            lambda s: s['scope']['resolutions'].reverse(),
            lambda s: s['scope']['resolutions'][-1].pop('returned_uniprot'),
            lambda s: s['scope']['resolutions'][0].update(returned_uniprot='P01116'),
            lambda s: s['scope']['resolutions'][0].update(status='not_found'),
            lambda s: s['scope']['resolutions'][0].update(status='identity_mismatch'),
            lambda s: s['scope']['resolutions'][0].update(status='unknown'),
            lambda s: s['targets'].pop(),
            lambda s: s['targets'].append(deepcopy(s['targets'][0])),
            lambda s: s['targets'][0].update(uniprot='P01116'),
        ]
        for index, modify in enumerate(modifications):
            with self.subTest(case=index):
                snapshot = fixture()
                modify(snapshot)
                with self.assertRaises(ValueError):
                    verify_snapshot(resign(snapshot))

    def test_civic_scope_is_not_silently_attached_to_disease_free_cohort(self):
        with self.assertRaisesRegex(ValueError, 'CIViC enrichment is not supported'):
            build_graph(fixture(), civic_snapshot={})

    def test_construction_request_and_plan_are_preserved_without_mutating_source(self):
        snapshot = fixture()
        snapshot['construction'] = {'policy': 'test', 'request': {'question': 'Test only'}, 'plan': {'families': ['ppis']}}
        graph = build_graph(resign(snapshot))
        self.assertEqual(graph['construction'], snapshot['construction'])
        graph['construction']['plan']['families'].append('go')
        self.assertEqual(snapshot['construction']['plan']['families'], ['ppis'])

    def test_save_and_replay_use_existing_graph_publication_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, replay = Path(tmp) / 'first', Path(tmp) / 'replay'
            graph = save_run(fixture(), first)
            snapshot = json.loads((first / 'snapshot.json').read_text())
            self.assertEqual(graph, save_run(snapshot, replay, run_mode='replay'))
            self.assertEqual(json.loads((first / 'cohort_scope.json').read_text()), snapshot['scope'])
            self.assertEqual(json.loads((first / 'target_resolution.json').read_text()), snapshot['scope']['resolutions'])
            manifest = json.loads((first / 'run_manifest.json').read_text())
            self.assertEqual(manifest['scope'], snapshot['scope'])
            self.assertFalse(manifest['biological_validation_performed'])
            self.assertFalse(manifest['llm_used'])
            trace = json.loads((first / 'pipeline_trace.json').read_text())
            self.assertEqual(trace[0]['step'], 'select_protein_cohort')
            for name in ['graph.json', 'assertions.json', 'nodes.tsv', 'edges.tsv', 'report.html', 'benchmark_readiness.json']:
                self.assertTrue((first / name).is_file(), name)

    def test_existing_disease_graph_and_question_basis_remain_byte_equivalent(self):
        snapshot = demo_snapshot()
        snapshot['created_at'] = '2026-10-23T00:00:00+00:00'
        graph = build_graph(resign(snapshot))
        self.assertNotIn('scope', graph)
        self.assertEqual(digest(graph), '15190119aee9e2c83f1bb501afc5fac7fc152d0cd587e8f126426261598aaf3b')
        self.assertEqual(graph['question_basis_sha256'], '4d9ee5ffc4f1941abf28dd424e2e86942c9f8362c9b4ca6727707dd2b3dd6938')


if __name__ == '__main__':
    unittest.main()
