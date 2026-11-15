"""Public expert-gold projection controls using invented clinical claims."""
from copy import deepcopy
import unittest

from tools.reference_accuracy.civic_fact_gold import (
    FIELDS, WORDS, ROUND, apply_to_graph, human_final_label, match_projection, reference_projection,
)


def fixture():
    data = ['GENE Invented', 'PREDICTIVE', 'resistance', 'Drug A and Drug B', 'Invented Disease']
    claim = {'type': 'table', 'content': [[k, v] for k, v in zip(FIELDS, data)],
        'meta': {'synonyms': [{'type': 'therapy', 'name': n, 'xrefs': 'NCI:'+x}
            for n, x in [('Drug A', 'C1'), ('Drug B', 'C2')]]}}
    row = {'id': 'invented-row', 'display_id': 'invented-display', 'civic.id': '123',
        'document.pmid': '99999999', 'claim.hash': 4, 'evidence.hash': 5,
        'claim': [claim], 'claim.flat': '; '.join(w+' is '+v for w, v in zip(WORDS, data)),
        'claim.source': 'civic', 'claim.generated': False, 'evidence.generated': False,
        'gold_label_name': 'SUPPORTS', 'evidence.flat': 'Invented reference evidence.',
        'reviews': [{'username': 'creisle', 'round': ROUND, 'label': 'SUPPORTS',
                     'reason': 'Invented human explanation.', 'original_label': 'NEI'}]}
    raw = {**{k: row[k] for k in ('id', 'display_id', 'civic.id', 'document.pmid', 'claim.hash', 'evidence.hash',
        'claim.generated', 'evidence.generated', 'claim.source')},
        'gold_label_name': 'NEI', 'label': ['SUPPORTS. Invented human explanation.', '[invented_model] REFUTES. Model output.']}
    record = {'id': 123, 'molecularProfile': {'name': data[0]}, 'evidenceType': data[1],
        'significance': 'RESISTANCE', 'therapies': [{'name': n, 'ncitId': x}
            for n, x in [('Drug B', 'C2'), ('Drug A', 'C1')]], 'disease': {'name': data[4]},
        'evidenceDirection': 'SUPPORTS', 'variantOrigin': 'SOMATIC', 'therapyInteractionType': 'COMBINATION',
        'description': 'Invented reference evidence.',
        'source': {'sourceType': 'PUBMED', 'citationId': '99999999'}}
    edge = {'id': 'edge1', 'assertion_id': 'assertion1', 'record_kind': 'variant_therapy_response',
        'evidence_record': record, 'aggregator': 'CIViC', 'data_kind': 'curated_source'}
    return row, raw, edge


class CivicFactHumanGoldTests(unittest.TestCase):
    def test_actual_human_tag_is_distinct_from_bracketed_model_outputs(self):
        row, raw, _ = fixture()
        self.assertEqual(human_final_label(row, raw), 'SUPPORTS')
        raw['label'] = ['[model] SUPPORTS. Invented human explanation.']
        with self.assertRaises(ValueError): human_final_label(row, raw)

    def test_augmented_bot_conflicting_or_unreleased_label_cannot_become_gold(self):
        for change in ('augmented', 'raw_augmented', 'bot', 'round', 'released', 'identity', 'old_label'):
            row, raw, _ = fixture()
            if change == 'augmented': row['claim.generated'] = True
            if change == 'raw_augmented': raw['evidence.generated'] = True
            if change == 'bot': row['reviews'][0]['username'] = 'bot'
            if change == 'round': row['reviews'][0]['round'] = 'different'
            if change == 'released': row['gold_label_name'] = 'NEI'
            if change == 'identity': raw['evidence.hash'] += 1
            if change == 'old_label': raw['gold_label_name'] = 'REFUTES'
            with self.subTest(change=change), self.assertRaises(ValueError): human_final_label(row, raw)

    def test_complete_profile_publication_and_whole_therapy_set_match(self):
        row, _, edge = fixture(); projection = reference_projection(row)
        self.assertEqual(match_projection(edge['evidence_record'], projection, row['document.pmid'], row['evidence.flat']), [])
        for change in ('profile', 'drug_subset', 'publication', 'direction', 'evidence_passage'):
            record = deepcopy(edge['evidence_record'])
            if change == 'profile': record['molecularProfile']['name'] += ' AND NOT OtherVariant'
            if change == 'drug_subset': record['therapies'].pop()
            if change == 'publication': record['source']['citationId'] = '11111111'
            if change == 'direction': record['evidenceDirection'] = 'DOES_NOT_SUPPORT'
            if change == 'evidence_passage': record['description'] += ' New conflicting result.'
            with self.subTest(change=change): self.assertTrue(match_projection(record, projection, row['document.pmid'], row['evidence.flat']))

    def test_inconsistent_flat_claim_duplicate_fields_or_therapy_aliases_fail(self):
        for change in ('flat', 'duplicate', 'therapy_subset', 'xref'):
            row, _, _ = fixture()
            if change == 'flat': row['claim.flat'] = row['claim.flat'].replace('resistance', 'sensitivity')
            if change == 'duplicate': row['claim'][0]['content'].append(['significance', 'resistance'])
            if change == 'therapy_subset': row['claim'][0]['meta']['synonyms'].pop()
            if change == 'xref': row['claim'][0]['meta']['synonyms'][0]['xrefs'] = 'CHEMBL:invented'
            with self.subTest(change=change), self.assertRaises(ValueError): reference_projection(row)

    def test_partial_label_does_not_validate_omitted_context_or_full_assertion(self):
        row, raw, edge = fixture()
        labels, audit = apply_to_graph({'edges': [edge]}, [row], [raw], retained_edge_ids={'edge1'})
        self.assertEqual(labels[0]['benchmark_projection_label'], 'SUPPORTS')
        self.assertEqual(labels[0]['whole_assertion_scientific_correctness'], 'unknown')
        self.assertTrue(labels[0]['matched_gold_rows'][0]['current_description_equals_reference_evidence'])
        self.assertIn('variantOrigin', labels[0]['outside_benchmark_context_unassessed'])
        self.assertEqual(audit['qualified_human_reference_rows'], 1)

    def test_changed_evidence_passage_keeps_current_record_unknown(self):
        row, raw, edge = fixture(); edge['evidence_record']['description'] += ' Different result.'
        labels, _ = apply_to_graph({'edges': [edge]}, [row], [raw])
        self.assertEqual(labels[0]['benchmark_projection_label'], 'unknown')
        self.assertEqual(labels[0]['matched_gold_rows'], [])
        self.assertIn('current_evidence_passage', labels[0]['candidate_context_checks'][0]['mismatching_fields'])

    def test_unmatched_and_parallel_records_stay_in_original_denominator(self):
        row, raw, edge = fixture(); other = deepcopy(edge)
        other['id'] = 'edge2'; other['evidence_record']['id'] = 456
        labels, _ = apply_to_graph({'edges': [edge, other]}, [row], [raw], retained_edge_ids=set())
        self.assertEqual(len(labels), 2)
        self.assertEqual([x['benchmark_projection_label'] for x in labels], ['SUPPORTS', 'unknown'])
        self.assertEqual({x['assertion_id'] for x in labels}, {'assertion1'})
        self.assertFalse(labels[0]['retained_source_edge'])

    def test_reference_labels_include_unfavorable_NEI_and_refutation(self):
        for label in ('REFUTES', 'NEI'):
            row, raw, edge = fixture(); row['gold_label_name'] = label
            row['reviews'][0]['label'] = label; raw['label'][0] = label+'. Invented human explanation.'
            labels, _ = apply_to_graph({'edges': [edge]}, [row], [raw])
            self.assertEqual(labels[0]['benchmark_projection_label'], label)


if __name__ == '__main__': unittest.main()
