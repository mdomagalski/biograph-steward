"""Invented native annotations test source-bound question and review semantics."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from biograph_steward.assertions import build_assertions
from biograph_steward.client import digest
from biograph_steward.go_qualification import GAF_FIELDS, native_record
from biograph_steward.goa_questions import answer_native_go_question

PROTEIN = 'UniProtKB:P12345'
OTHER = 'UniProtKB:Q12345'
SOURCE = 'a' * 64
PUBLICATION = 'b' * 64


def make_native(line, *, protein=PROTEIN, relation='acts_upstream_of', term='GO:0000001', aspect='P', references=None):
    fields = ['UniProtKB', protein.split(':')[1], 'INVENTED', relation, term,
              references or 'PMID:' + str(100 + line), 'IDA', '', aspect, 'Synthetic protein', '',
              'protein', 'taxon:9606', '20260101', 'SYNTHETIC', '', '']
    list_fields = {'Qualifier', 'DB:Reference', 'With', 'Synonym', 'Taxon_ID'}
    parsed = {key: (value.split('|') if value else []) if key in list_fields else value
              for key, value in zip(GAF_FIELDS, fields)}
    return native_record(line, '\t'.join(fields), fields, parsed, SOURCE)


def fixture(first_references=None):
    graph = {'graph_format': 'invented-native-GO-fixture', 'data_kind': 'synthetic_demo',
        'snapshot_sha256': 'c' * 64, 'review_events': [], 'targets': [{'id': PROTEIN}, {'id': OTHER}],
        'nodes': [{'id': PROTEIN, 'category': 'biolink:Protein', 'sym': 'Invented protein'},
                  {'id': OTHER, 'category': 'biolink:Protein', 'sym': 'Other protein'},
                  {'id': 'GO:0000001', 'category': 'biolink:BiologicalProcess', 'name': 'Invented process'},
                  {'id': 'GO:0000002', 'category': 'biolink:MolecularActivity', 'name': 'Invented activity'}],
        'evidence_extension_sha256': 'd' * 64,
        'evidence_extension': {'sources': {'goa': {'publication_sha256': PUBLICATION}}},
        'edges': [], 'extension_observations': []}
    native = [make_native(1, references=first_references), make_native(2), make_native(3, relation='involved_in'),
              make_native(4, relation='enables', term='GO:0000002', aspect='F'), make_native(5, protein=OTHER)]
    for n in native:
        oid = 'goa.observation:' + digest(n)[:24]
        eid = 'edge:' + digest({'native': n['id']})[:20]
        record = {'id': oid, 'source_kind': 'goa', 'subject': n['subject'], 'go_id': n['go_id'],
            'go_label': 'Invented activity' if n['aspect'] == 'F' else 'Invented process',
            'relation_literal': n['relation_literal'], 'evidence_code': n['evidence_code'],
            'assigned_by': n['assigned_by'], 'publications': n['reference_identifiers'],
            'source_publication_sha256': PUBLICATION,
            'source': {'kind': 'goa', 'publication_sha256': PUBLICATION},
            'citations': [{'id': ref,
                'url': 'https://pubmed.ncbi.nlm.nih.gov/' + ref.split(':')[1] + '/' if ref.startswith('PMID:') else None,
                'role': 'native_annotation_reference_identifier',
                'interpretation': 'Identifiers on one native GAF row can alias one cited reference.'}
                for ref in n['reference_identifiers']],
            'native_record': deepcopy(n), 'graph_edge_id': eid, 'local_review_state': 'candidate',
            'biologically_validated': False}
        graph['extension_observations'].append(deepcopy(record))
        graph['edges'].append({'id': eid, 'subject': n['subject'], 'object': n['go_id'],
            'record_kind': 'native_go_annotation', 'predicate': 'biograph:has_native_go_annotation',
            'extension_source_kind': 'goa', 'source_publication_sha256': PUBLICATION,
            'extension_publication_sha256': PUBLICATION, 'snapshot_sha256': graph['snapshot_sha256'],
            'qualifiers': {'go_aspect': n['aspect'], 'go_relation': n['relation_literal'], 'species': 'NCBITaxon:9606'},
            'status': 'passed_structural_checks', 'review_reasons': [], 'primary_source_raw': n['assigned_by'],
            'evidence_record': deepcopy(record), 'observation': deepcopy(record),
            'record_locators': ['source/annotations.gaf.gz#line=' + str(n['source_line'])],
            'source_record_count': 1, 'publications': n['reference_identifiers'],
            'data_kind': 'published_database_annotations', 'biologically_validated': False})
    graph['assertions'] = build_assertions(graph)
    return graph


def observation(graph, line=1):
    return next(r for r in graph['extension_observations'] if r['native_record']['source_line'] == line)


def edge_for(graph, line=1):
    return next(r for r in graph['edges'] if r['id'] == observation(graph, line)['graph_edge_id'])


def assertion_for(graph, line=1):
    return next(r for r in graph['assertions'] if r['id'] == edge_for(graph, line)['assertion_id'])


class NativeGoQuestionTests(unittest.TestCase):
    def setUp(self):
        self.graph = fixture()

    def test_relations_stay_distinct_and_two_papers_group_under_one_assertion(self):
        result = answer_native_go_question(self.graph, PROTEIN)
        self.assertEqual(result['summary']['matching_concepts'], 3)
        self.assertEqual(result['summary']['matching_native_records'], 4)
        upstream = next(c for c in result['concepts'] if c['relation_literal'] == 'acts_upstream_of')
        self.assertEqual(upstream['native_record_count'], 2)
        self.assertEqual({c['relation_literal'] for c in result['concepts']}, {'acts_upstream_of', 'involved_in', 'enables'})
        self.assertNotIn('disease', result['concepts'][0])

    def test_candidate_support_never_implies_accepted_review(self):
        self.assertEqual(answer_native_go_question(self.graph, PROTEIN, view='accepted')['records'], [])
        assertion_for(self.graph)['lifecycle_state'] = 'accepted'
        result = answer_native_go_question(self.graph, PROTEIN, view='accepted')
        self.assertEqual(result['summary']['matching_concepts'], 1)
        self.assertEqual(len(result['records']), 2)
        self.assertTrue(all(r['local_review_state'] == 'accepted' for r in result['records']))
        self.assertTrue(all(r['source_observation']['local_review_state'] == 'candidate' for r in result['records']))

    def test_search_pages_and_counts_use_native_fields_not_generic_limits(self):
        result = answer_native_go_question(self.graph, PROTEIN, search='PMID:101')
        self.assertEqual(len(result['records']), 1)
        self.assertEqual(result['records'][0]['source_line'], 1)
        self.assertEqual(answer_native_go_question(self.graph, PROTEIN, search='disease')['records'], [])
        first = answer_native_go_question(self.graph, PROTEIN, limit=2)
        second = answer_native_go_question(self.graph, PROTEIN, offset=2, limit=2)
        self.assertEqual(first['summary']['next_offset'], 2)
        self.assertIsNone(second['summary']['next_offset'])
        self.assertEqual(len({r['assertion_id'] for r in first['concepts'] + second['concepts']}), 3)

    def test_complete_native_source_and_answers_are_nonmutating(self):
        before = deepcopy(self.graph)
        with patch('urllib.request.urlopen', side_effect=AssertionError('No retrieval')):
            result = answer_native_go_question(self.graph, PROTEIN, source_run='invented_goa')
        self.assertEqual(result['content_sha256'], digest({k: v for k, v in result.items() if k != 'content_sha256'}))
        self.assertEqual(result['source_run'], 'invented_goa')
        for row in result['records']:
            source = observation(self.graph, row['source_line'])
            self.assertEqual(row['source_observation'], source)
            self.assertEqual(len(row['native_record']['raw_fields']), 17)
            self.assertEqual(row['source_gaf_sha256'], SOURCE)
        result['records'][0]['native_record']['raw_fields'][2] = 'changed'
        self.assertEqual(self.graph, before)

    def test_gold_retention_metadata_does_not_rewrite_native_record(self):
        for record in self.graph['extension_observations']:
            record['retention'] = {'baseline_graph_edge_id': record['graph_edge_id'], 'decision': 'abstain'}
        result = answer_native_go_question(self.graph, PROTEIN)
        self.assertEqual(len(result['records']), 4)
        self.assertNotIn('retention', result['records'][0]['source_observation'])
        self.assertEqual(result['records'][0]['retention']['decision'], 'abstain')

    def test_explicit_pruning_is_not_a_missing_native_source_error(self):
        record = observation(self.graph, 4); eid = record['graph_edge_id']; aid = edge_for(self.graph, 4)['assertion_id']
        record['retention'] = {'baseline_graph_edge_id': eid, 'decision': 'prune'}; record['graph_edge_id'] = None
        self.graph['edges'] = [e for e in self.graph['edges'] if e['id'] != eid]
        self.graph['assertions'] = [a for a in self.graph['assertions'] if a['id'] != aid]
        result = answer_native_go_question(self.graph, PROTEIN)
        self.assertEqual(result['summary']['pruned_source_observations'], 1)
        self.assertEqual(result['summary']['matching_concepts'], 2)

    def test_rejected_records_do_not_leak_into_candidate_view(self):
        assertion_for(self.graph)['lifecycle_state'] = 'rejected'
        result = answer_native_go_question(self.graph, PROTEIN)
        self.assertEqual(result['summary']['anchored_source_records'], 4)
        self.assertEqual(result['summary']['inspectable_records_in_view'], 2)

    def test_wrong_scope_and_parameters_fail(self):
        for protein, kwargs in [('Invented protein', {}), ('P12345', {}), ('UniProtKB:missing', {}),
                                (PROTEIN, {'view': 'all'}), (PROTEIN, {'offset': True}),
                                (PROTEIN, {'limit': 26}), (PROTEIN, {'search': None}),
                                (PROTEIN, {'source_run': '../bad'})]:
            with self.subTest(protein=protein, kwargs=kwargs), self.assertRaises(ValueError):
                answer_native_go_question(self.graph, protein, **kwargs)

    def test_old_pharos_annotation_is_not_a_native_source_addition(self):
        g = deepcopy(self.graph); g['evidence_extension']['sources'].pop('goa')
        g['edges'][0]['record_kind'] = 'go_annotation'
        with self.assertRaisesRegex(ValueError, 'no verified native GO'):
            answer_native_go_question(g, PROTEIN)

    def test_reference_identifiers_cannot_acquire_missing_or_wrong_links(self):
        for change in ('missing', 'wrong_pmid', 'unrelated_safe_url'):
            g = deepcopy(self.graph); source = observation(g)
            if change == 'missing': source['citations'] = []
            elif change == 'wrong_pmid': source['citations'][0]['url'] = 'https://pubmed.ncbi.nlm.nih.gov/999/'
            else: source['citations'][0]['url'] = 'https://example.org/unrelated'
            edge_for(g)['evidence_record'] = deepcopy(source); edge_for(g)['observation'] = deepcopy(source)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'citations'):
                answer_native_go_question(g, PROTEIN)

    def test_unknown_reference_alias_stays_a_literal_without_an_invented_link(self):
        result = answer_native_go_question(fixture('PMID:101|OTHER:alias'), PROTEIN)
        row = next(r for r in result['records'] if r['source_line'] == 1)
        self.assertEqual(row['reference_identifiers'], ['PMID:101', 'OTHER:alias'])
        self.assertEqual(row['citations'][0]['url'], 'https://pubmed.ncbi.nlm.nih.gov/101/')
        self.assertIsNone(row['citations'][1]['url'])

    def test_source_edge_assertion_and_joint_display_tampering_fail(self):
        mutations = [
            lambda g: observation(g).update(relation_literal='involved_in'),
            lambda g: observation(g)['native_record'].update(source_line=99),
            lambda g: observation(g)['native_record']['raw_fields'].__setitem__(3, 'involved_in'),
            lambda g: edge_for(g).update(predicate='biolink:participates_in'),
            lambda g: edge_for(g)['qualifiers'].update(disease='MONDO:0000001'),
            lambda g: edge_for(g).update(extension_publication_sha256='0'*64),
            lambda g: assertion_for(g).update(revision='changed'),
            lambda g: assertion_for(g).update(evidence_extension_sha256='0'*64),
            lambda g: g['extension_observations'].append(deepcopy(observation(g))),
        ]
        for mutation in mutations:
            g = deepcopy(self.graph); mutation(g)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                answer_native_go_question(g, PROTEIN)
        g = deepcopy(self.graph)
        observation(g)['relation_literal'] = 'involved_in'
        edge_for(g)['evidence_record'] = deepcopy(observation(g))
        edge_for(g)['observation'] = deepcopy(observation(g))
        with self.assertRaisesRegex(ValueError, 'native row'):
            answer_native_go_question(g, PROTEIN)


if __name__ == '__main__':
    unittest.main()
