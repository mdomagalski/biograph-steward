"""Standalone tables must retain qualifications from invented source records."""
from copy import deepcopy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.assertions import new_review_event
from biograph_steward.civic_questions import answer_civic_question
from biograph_steward.graph import build_graph
from biograph_steward.questions import save_answer, verify_answer
from test_civic import CivicAPI, fixture


def export_rows(answer, directory):
    save_answer(answer, directory)
    with (Path(directory) / 'evidence_context.tsv').open(newline='') as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        return reader.fieldnames, list(reader)


class EvidenceContextExportTests(unittest.TestCase):
    def test_each_source_row_is_self_contained_without_changing_the_saved_answer(self):
        api = CivicAPI()
        api.rows = api.rows[:2]
        api.rows[1].update(significance='RESISTANCE', evidenceLevel='B')
        profile = api.rows[0]['molecularProfile']
        profile.update(isComplex=True, isMultiVariant=True, rawName='#VID81 AND #VID82')
        variant = deepcopy(profile['variants'][0])
        variant.update(id=82, name='Second invented variant')
        profile['variants'].append(variant)
        api.rows[1]['molecularProfile'] = deepcopy(profile)
        p, c = fixture(api)
        graph = build_graph(p, civic_snapshot=c)
        answer = answer_civic_question(graph, view='candidates', source_run='invented_source')
        self.assertEqual(len(answer['citations']), 1)  # Two records support one qualified assertion.
        before = deepcopy(answer)
        citation = answer['citations'][0]
        source_edges = {'CIViC.evidence:' + str(e['evidence_record']['id']): e
                        for e in citation['evidence_records']}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'export'
            _, rows = export_rows(answer, directory)
            self.assertEqual(json.loads((directory / 'question.json').read_text()), before)
            first_export = (directory / 'evidence_context.tsv').read_bytes()
            export_rows(answer, Path(tmp) / 'second_export')
            self.assertEqual((directory / 'evidence_context.tsv').read_bytes(), first_export)
            with self.assertRaisesRegex(ValueError, 'not empty'):
                save_answer(answer, directory)
        self.assertEqual(answer, before)
        verify_answer(answer)
        self.assertEqual(len(rows), 2)
        for row in rows:
            edge = source_edges[row['evidence_id']]
            record = edge['evidence_record']
            self.assertEqual(row['profile_id'], 'CIViC.molecularprofile:81')
            self.assertEqual(row['profile_name'], profile['name'])
            self.assertEqual(row['profile_expression'], '#VID81 AND #VID82')
            self.assertEqual(json.loads(row['profile_variants']), profile['variants'])
            self.assertEqual(row['disease_id'], 'DOID:9256')
            self.assertNotEqual(row['disease_id'], graph['disease_node_id'])
            self.assertEqual(row['disease_name'], record['disease']['name'])
            self.assertEqual(row['source_disease_id'], 'CIViC.disease:11')
            self.assertEqual(row['local_review_state'], 'candidate')
            self.assertEqual(row['source_status'], 'ACCEPTED')
            self.assertEqual(row['evidence_level'], record['evidenceLevel'])
            self.assertEqual(row['description'], record['description'])
            self.assertEqual(row['source_id'], 'CIViC.source:' + str(record['source']['id']))
            self.assertEqual(row['source_reference'], 'PMID:' + record['source']['citationId'])
            self.assertEqual(row['edge_id'], edge['id'])
            self.assertEqual(json.loads(row['record_locators']), edge['record_locators'])
            self.assertEqual(json.loads(row['retrieval_provenance']), edge['retrieval_provenance'])
            self.assertEqual(row['snapshot_sha256'], c['content_sha256'])
            self.assertEqual(row['answer_sha256'], before['answer_sha256'])
            self.assertEqual(row['graph_basis_sha256'], before['graph_basis_sha256'])
            self.assertEqual(row['source_run'], 'invented_source')

    def test_ingredient_filter_exports_complete_sets_and_keeps_their_semantics(self):
        for interaction in ['COMBINATION', 'SUBSTITUTES', 'SEQUENTIAL']:
            with self.subTest(interaction=interaction):
                api = CivicAPI()
                api.rows = [api.rows[-1]]
                record = api.rows[0]
                record.update(therapyInteractionType=interaction, evidenceDirection='DOES_NOT_SUPPORT')
                p, c = fixture(api)
                answer = answer_civic_question(build_graph(p, civic_snapshot=c),
                                               therapy='cetuximab', view='candidates')
                with tempfile.TemporaryDirectory() as tmp:
                    _, rows = export_rows(answer, Path(tmp))
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(json.loads(row['therapy_members']), record['therapies'])
                self.assertEqual(json.loads(row['therapy_ids']), ['CIViC.therapy:16', 'CIViC.therapy:28'])
                self.assertEqual(row['therapy_interaction'], interaction)
                self.assertEqual(row['therapy_set_id'], answer['citations'][0]['object'])
                self.assertIn('Cetuximab', row['therapy_label'])
                self.assertIn('Panitumumab', row['therapy_label'])
                self.assertEqual(row['evidence_direction'], 'DOES_NOT_SUPPORT')
                self.assertEqual(row['significance'], 'RESISTANCE')
                self.assertTrue(row['therapy_scope_note'])
                if interaction == 'SEQUENTIAL':
                    self.assertIn('order is not supplied', row['therapy_scope_note'])

    def test_accepted_export_uses_local_review_and_empty_view_does_not_export_candidates(self):
        p, c = fixture()
        graph = build_graph(p, civic_snapshot=c)
        with tempfile.TemporaryDirectory() as tmp:
            fields, empty_rows = export_rows(answer_civic_question(graph), Path(tmp) / 'empty')
            self.assertFalse(empty_rows)
            self.assertIn('local_review_state', fields)
            self.assertIn('source_status', fields)
            assertion = next(a for a in graph['assertions'] if a['kind'] == 'variant_therapy_response')
            event = new_review_event(graph, assertion['id'], 'accepted', 'Software test', 'Invented fixture only')
            reviewed = build_graph(p, [event], civic_snapshot=c)
            answer = answer_civic_question(reviewed)
            _, rows = export_rows(answer, Path(tmp) / 'accepted')
        self.assertTrue(rows)
        self.assertEqual({row['assertion_id'] for row in rows}, {assertion['id']})
        self.assertEqual({row['local_review_state'] for row in rows}, {'accepted'})
        self.assertEqual({row['source_status'] for row in rows}, {'ACCEPTED'})


if __name__ == '__main__':
    unittest.main()
