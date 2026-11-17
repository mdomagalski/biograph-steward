import unittest

from tools.reference_accuracy.ppi_gold import PRESENCE, WEIGHT, annotate_scores, gold_rows, graph_index, pair_key


def canonical(**updates):
    return {'base_accessions': ['P00001', 'P00002'], 'reference_label': 'positive',
            'eligible_canonical_gold': True,
            'exact_full_canonical_sequence_match': [True, True],
            'inferred_binding_region_sequence': False, 'pubmed_ids': ['1'], **updates}


def manual(**updates):
    return {'base_accession_pair': ['P00001', 'P00002'], 'reference_label': 'unknown',
            'positive_reference_rows': [{'curated': True}],
            'negative_reference_rows': [{'curated': True}],
            'positive_PMIDs': ['1'], 'negative_PMIDs': ['2'],
            'generic_functional_association_truth_label': False, **updates}


class PPIPublicGoldTests(unittest.TestCase):
    def test_literal_pair_direction_is_symmetric(self):
        self.assertEqual(pair_key(['UniProtKB:P00002', 'P00001']), ('P00001', 'P00002'))

    def test_isoform_state_cannot_be_silently_collapsed(self):
        for value in ('P00001-2', 'P00001_mutated', 'UniProtKB:', 'P00001|P00002'):
            with self.assertRaises(ValueError):
                pair_key([value, 'P00002'])

    def test_noncanonical_proteoform_cannot_enter_wildtype_gold(self):
        with self.assertRaises(ValueError):
            gold_rows([canonical(exact_full_canonical_sequence_match=[True, False])], 'canonical_sequence')

    def test_designed_binding_region_variant_is_not_experimental_negative(self):
        with self.assertRaises(ValueError):
            gold_rows([canonical(reference_label='negative', inferred_binding_region_sequence=True)], 'canonical_sequence')

    def test_conflicting_curations_stay_unknown(self):
        self.assertIsNone(gold_rows([manual()], 'manual_gene_pair')[0]['gold'])
        with self.assertRaises(ValueError):
            gold_rows([manual(reference_label='negative')], 'manual_gene_pair')

    def test_no_support_record_is_not_negative_gold(self):
        with self.assertRaises(ValueError):
            gold_rows([manual(reference_label='negative', positive_reference_rows=[], negative_reference_rows=[])], 'manual_gene_pair')

    def test_nonedge_changes_presence_prediction_without_creating_gold_or_weight(self):
        reference = gold_rows([canonical()], 'canonical_sequence')
        row = annotate_scores(reference, {'P00001', 'P00002'}, {})[0]
        self.assertEqual(row['gold'], 1)
        self.assertEqual(row['scores'][PRESENCE], 0)
        self.assertIsNone(row['scores'][WEIGHT])
        self.assertEqual(row['weight_unavailable_reason'], 'no_native_pair_weight_returned')

    def test_native_explicit_zero_weight_remains_available(self):
        reference = gold_rows([canonical(reference_label='negative')], 'canonical_sequence')
        row = annotate_scores(reference, {'P00001', 'P00002'}, {('P00001', 'P00002'): 0.0})[0]
        self.assertEqual(row['scores'][PRESENCE], 1)
        self.assertEqual(row['scores'][WEIGHT], 0.0)
        self.assertIsNone(row['weight_unavailable_reason'])

    def test_self_and_unknown_source_protein_remain_unavailable(self):
        for accessions in (['P00001', 'P00001'], ['P00001', 'P00003']):
            row = annotate_scores(gold_rows([canonical(base_accessions=accessions)], 'canonical_sequence'),
                                  {'P00001', 'P00002'}, {})[0]
            self.assertIsNone(row['scores'][PRESENCE])
            self.assertIsNone(row['scores'][WEIGHT])
            self.assertEqual(row['gold'], 1)

    def test_duplicate_or_nonfinite_native_pairs_are_rejected(self):
        for pairs in ([['P00001', 'P00002', .5], ['P00002', 'P00001', .6]],
                      [['P00001', 'P00002', float('nan')]]):
            with self.assertRaises(ValueError):
                graph_index({'nodes': ['P00001', 'P00002'], 'pairs': pairs})


if __name__ == '__main__':
    unittest.main()
