"""Invented scope records only; no real study or reserved outcome access."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_biological_comparison_scope as scope
from test_lambourne_corroboration import lookup_row, assay_row


class ComparisonScopeTests(unittest.TestCase):
    def setUp(self):
        self.lookup = [lookup_row(0, huri=True), lookup_row(1, scope.assessment.STATES[1]),
                       lookup_row(2, scope.assessment.STATES[2]), lookup_row(3)]
        self.comparator = scope.assessment.make_comparator(self.lookup)
        self.assays = [assay_row(comp, status) for comp, status in zip(self.comparator,
            ['detected', 'not_detected', 'not_detected', 'failed_sequence_confirmation'])]
        for assay, comp in zip(self.assays, self.comparator):
            assay.update({key: comp['identity'][key] for key in ('ad_orf_id', 'db_orf_id')})
        self.rows = scope.assessment.join_assay(self.comparator, self.assays)
        self.inventory = {'pairs': [[[['uniprotkb', 'P00000']], [['uniprotkb', 'P00001']]],
            [[['uniprotkb', 'P00002'], ['uniprotkb', 'P00003']], [['uniprotkb', 'P00000']]] ]}

    def test_all_pairs_and_distinct_eligibility_preserved_without_detection_labels(self):
        result = scope.project_candidates(self.lookup, self.rows, self.inventory)
        self.assertEqual(len(result), 4)
        self.assertEqual(sum(row['assay_eligible'] for row in result), 3)
        self.assertEqual(sum(row['historical_pharos_comparator_eligible'] for row in result), 2)
        self.assertEqual(result[3]['assay_exclusion_reason'], 'failed_sequence_confirmation')
        self.assertIsNone(result[0]['assay_exclusion_reason'])
        self.assertTrue(result[0]['exposure']['consumed_intact_exact_pair'])
        self.assertFalse(result[1]['exposure']['consumed_intact_exact_pair'])
        for key in ('detected', 'not_detected', 'published_result', 'raw_final_score'):
            self.assertNotIn('"' + key + '"', json.dumps(result))
        self.assertEqual(result[0]['constructs']['ad_orf_id'], '1')
        self.assertFalse(result[0]['constructs']['protein_to_construct_orientation_inferred'])

    def test_eligible_detection_outcome_does_not_change_candidate_projection(self):
        original = scope.project_candidates(self.lookup, self.rows, self.inventory)
        changed = deepcopy(self.rows)
        changed[0]['assay'].update(assay_status='not_detected', detected=False)
        self.assertEqual(original, scope.project_candidates(self.lookup, changed, self.inventory))

    def test_same_pair_wrong_source_row_or_construct_rejected(self):
        for key, value in [('source_row', 99), ('ad_orf_id', 'not-the-assayed-construct')]:
            rows = deepcopy(self.rows); rows[0]['assay'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                scope.project_candidates(self.lookup, rows, self.inventory)

    def test_missing_duplicate_or_changed_comparator_rows_rejected(self):
        alternatives = [self.rows[:-1], self.rows + [self.rows[0]], list(reversed(self.rows))]
        changed = deepcopy(self.rows); changed[0]['comparator']['pharos_status'] = 'invented'
        alternatives.append(changed)
        for rows in alternatives:
            with self.assertRaises(ValueError):
                scope.project_candidates(self.lookup, rows, self.inventory)

    def test_only_exact_singleton_namespace_identity_counts_as_intact_overlap(self):
        self.assertEqual(scope.exact_intact_pairs(self.inventory), {('P00000', 'P00001')})
        variants = {'pairs': [[[['uniprotkb', 'P00000-2']], [['uniprotkb', 'P00001']]],
                              [[['intact', 'P00000']], [['uniprotkb', 'P00001']]]]}
        self.assertEqual(scope.exact_intact_pairs(variants), {('P00000-2', 'P00001')})
        with self.assertRaises(ValueError):
            scope.exact_intact_pairs({'pairs': [['not a participant pair']]})

    def test_provider_bundle_local_nid_and_scores_are_not_miscore_prerequisites(self):
        rows = deepcopy(self.lookup)
        for row in rows:
            for match in row['pharos_matches']['raw']:
                match['record'].update(nid=1, props=[{'name': 'Score', 'value': '0.8'},
                    {'name': 'p_int', 'value': '0.9'}, {'name': 'Data Source', 'value': 'STRINGDB'}])
        availability = scope.field_availability(rows)
        self.assertEqual(availability['matching_source_views'], 2)
        self.assertEqual(availability['source_property_name_counts']['Score'], 2)
        self.assertEqual(availability['source_record_field_counts'], {'nid': 2, 'props': 2, 'type': 2})
        self.assertTrue(all(count == 0 for count in availability['MImerge_MIscore_prerequisite_literal_field_counts'].values()))
        rows[0]['pharos_matches']['raw'][0]['record']['props'].append({'name': 'MIscore', 'value': '0.8'})
        self.assertEqual(scope.field_availability(rows)['MImerge_MIscore_prerequisite_literal_field_counts']['MIscore'], 1)

    def test_false_or_missing_eligibility_cannot_be_coerced(self):
        for value in ('true', None, False):
            rows = deepcopy(self.rows); rows[0]['assay']['evaluable'] = value
            with self.assertRaises(ValueError):
                scope.project_candidates(self.lookup, rows, self.inventory)


if __name__ == '__main__':
    unittest.main()
