"""Cohort paths preserve evidence and review state without inventing disease links."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest
from biograph_steward.graph import build_graph
from biograph_steward.questions import (
    COHORT_TEMPLATE, TEMPLATE, answer_html, answer_question, answer_text, save_answer, verify_answer,
)
from test_questions import fixture as disease_fixture, review
from test_normalization import resign


def fixture():
    snapshot = disease_fixture()
    ids = [row['uniprot'] for row in snapshot['targets']]
    for row in snapshot['targets']:
        row.pop('diseaseAssociationDetails')
    snapshot['disease'] = None
    snapshot['scope'] = {
        'kind': 'protein_cohort', 'name': 'Explicit test proteins',
        'requested_uniprot': ids + ['Q5TEC6'],
        'resolutions': [{'requested_uniprot': uid, 'status': 'resolved', 'returned_uniprot': uid} for uid in ids]
                       + [{'requested_uniprot': 'Q5TEC6', 'status': 'not_found', 'returned_uniprot': None}],
    }
    return resign(snapshot)


class CohortQuestionTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = fixture()
        self.graph = build_graph(self.snapshot)

    def test_cohort_template_is_selected_without_a_synthetic_disease(self):
        answer = answer_question(self.graph, 'P04637', view='candidates', max_paths=5)
        self.assertEqual(answer['template'], COHORT_TEMPLATE)
        self.assertIsNone(answer['plan']['disease'])
        self.assertEqual(answer['plan']['scope'], self.graph['scope'])
        self.assertEqual(answer['returned_proteins'], 3)
        self.assertFalse(any(node['category'] == 'biolink:Disease' for node in answer['nodes']))
        self.assertNotIn('associated with', answer['question'])
        self.assertFalse(any('exact-term association' in row['text'] for row in answer['summary']))

    def test_interaction_path_contains_only_endpoints_and_interaction_evidence(self):
        answer = answer_question(self.graph, 'P04637', view='candidates', relations=['interactions'])
        self.assertEqual(answer['returned_proteins'], 2)
        citations = {row['id']: row for row in answer['citations']}
        for result in answer['results']:
            path = result['paths'][0]
            self.assertEqual(path['node_ids'], ['UniProtKB:P04637', result['protein']['id']])
            self.assertEqual(len(path['assertion_ids']), 1)
            self.assertEqual(citations[path['citation_ids'][0]]['kind'], 'protein_interaction')
        self.assertTrue(all('interaction annotation' in row['text'] for row in answer['summary']))

    def test_shared_pathway_has_two_memberships_with_no_disease_requirement(self):
        answer = answer_question(self.graph, 'P04637', view='candidates', relations=['shared_pathways'], max_paths=5)
        self.assertEqual({row['protein']['id'] for row in answer['results']}, {'UniProtKB:P00533', 'UniProtKB:P01116'})
        self.assertTrue(all(c['kind'] == 'pathway_membership' for c in answer['citations']))
        for result in answer['results']:
            for path in result['paths']:
                self.assertEqual(len(path['node_ids']), 3)
                self.assertEqual(path['node_ids'][0], 'UniProtKB:P04637')
                self.assertTrue(path['node_ids'][1].startswith('REACT:'))
                self.assertEqual(path['node_ids'][2], result['protein']['id'])
                self.assertEqual(len(path['assertion_ids']), 2)
                sentence = next(row for row in answer['summary'] if row['path_id'] == path['id'])
                self.assertIn(path['node_ids'][1], sentence['text'])

    def test_every_statement_cites_every_path_assertion_and_preserves_full_source_records(self):
        answer = answer_question(self.graph, 'P04637', view='candidates', max_paths=5)
        refs = {row['id']: row for row in answer['citations']}
        paths = {path['id']: path for row in answer['results'] for path in row['paths']}
        edges = {row['id']: row for row in self.graph['edges']}
        for row in answer['summary']:
            self.assertEqual([refs[cid]['assertion_id'] for cid in row['citation_ids']], paths[row['path_id']]['assertion_ids'])
        for citation in refs.values():
            self.assertTrue(citation['evidence_records'])
            for edge in citation['evidence_records']:
                self.assertEqual(edge, edges[edge['id']])
                self.assertEqual(edge['snapshot_sha256'], self.graph['snapshot_sha256'])
                self.assertTrue(edge['record_locators'])

    def test_default_accepted_view_never_promotes_candidates(self):
        answer = answer_question(self.graph, 'P04637')
        self.assertFalse(answer['results'])
        self.assertFalse(answer['summary'])
        self.assertEqual(answer['availability']['accepted_paths'], 0)
        self.assertEqual(answer['availability']['inspectable_proteins'], 3)

    def test_both_shared_memberships_must_be_accepted(self):
        path = answer_question(self.graph, 'P04637', view='candidates', relations=['shared_pathways'])['results'][0]['paths'][0]
        graph = review(self.snapshot, path['assertion_ids'][:1])
        self.assertFalse(answer_question(graph, 'P04637', relations=['shared_pathways'])['results'])
        graph = review(self.snapshot, path['assertion_ids'])
        answer = answer_question(graph, 'P04637', relations=['shared_pathways'])
        self.assertEqual(answer['returned_proteins'], 1)
        self.assertTrue(all(row['review_state'] == 'accepted' for row in answer['citations']))

    def test_rejected_context_cannot_form_a_candidate_path(self):
        path = answer_question(self.graph, 'P04637', view='candidates', relations=['interactions'])['results'][0]['paths'][0]
        graph = review(self.snapshot, path['assertion_ids'], state='rejected')
        answer = answer_question(graph, 'P04637', view='candidates', relations=['interactions'])
        self.assertNotIn(path['id'], {p['id'] for row in answer['results'] for p in row['paths']})

    def test_unresolved_proteins_and_missing_family_coverage_remain_explicit(self):
        answer = answer_question(self.graph, 'P04637', view='candidates')
        self.assertTrue(any('not resolved exactly' in row for row in answer['limitations']))
        self.assertTrue(any('unavailable' in row for row in answer['limitations']))
        self.assertIsNone(answer['plan']['selected_coverage']['ppis'])
        self.assertEqual(answer['plan']['scope']['resolutions'][-1]['requested_uniprot'], 'Q5TEC6')
        with self.assertRaisesRegex(ValueError, 'outside'):
            answer_question(self.graph, 'Q5TEC6')

    def test_wrong_scope_template_and_invalid_controls_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'scope'):
            answer_question(self.graph, 'P04637', template=TEMPLATE)
        with self.assertRaisesRegex(ValueError, 'scope'):
            answer_question(build_graph(disease_fixture()), 'P04637', template=COHORT_TEMPLATE)
        for kwargs in [{'view': 'all'}, {'max_results': True}, {'max_paths': 0}, {'relations': ['physical_binding']}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                answer_question(self.graph, 'P04637', **kwargs)

    def test_saved_answers_are_deterministic_and_escape_cohort_names(self):
        graph = deepcopy(self.graph)
        graph['scope']['name'] = '</h1><script>bad</script>'
        before = deepcopy(graph)
        answer = answer_question(graph, 'P04637', view='candidates', max_results=1, max_paths=1)
        self.assertEqual(graph, before)
        self.assertEqual(answer, answer_question(graph, 'P04637', view='candidates', max_results=1, max_paths=1))
        self.assertEqual(answer['matching_proteins'], 3)
        self.assertEqual(answer['omitted_proteins'], 2)
        self.assertNotIn('<script>bad</script>', answer_html(answer))
        self.assertIn('&lt;script&gt;', answer_html(answer))
        self.assertIn('[E001]', answer_text(answer))
        with tempfile.TemporaryDirectory() as tmp:
            save_answer(answer, Path(tmp) / 'question')
            loaded = json.loads((Path(tmp) / 'question/question.json').read_text())
            verify_answer(loaded)
            self.assertEqual(loaded, answer)

    def test_existing_disease_answer_is_byte_equivalent(self):
        snapshot = disease_fixture()
        snapshot['created_at'] = '2026-10-23T00:00:00+00:00'
        # Mock introspection fields iterate a set; omit those envelopes so this
        # fixed historical answer also has the same hash across Python processes.
        snapshot['requests'] = []
        answer = answer_question(build_graph(resign(snapshot)), 'P04637', view='candidates', max_paths=5)
        self.assertEqual(answer['answer_sha256'], '6eb47bfe02ca5f35ce44c8c4c9a36d9550824306edcb63632dddba423373fdb4')
        self.assertEqual(digest(answer), 'c97700386bdd847190b9d8a7eaf9bb33e6dd69cf9094924281e517acd02ff0bf')


if __name__ == '__main__':
    unittest.main()
