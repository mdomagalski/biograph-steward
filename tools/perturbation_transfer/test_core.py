"""Meaningful numerical and identity checks; no scientific holdout data."""
import csv
import tempfile
import unittest
from pathlib import Path

from tools.perturbation_transfer.core import (
    complex_pairs, gene_mapping, profile_correlations, top_neighbors,
    paired_query_bootstrap,
)


class CoreTests(unittest.TestCase):
    def test_native_pearson_and_target_mask(self):
        import numpy as np
        from scipy.stats import pearsonr
        raw = np.array([[9., 1., 2., 4.], [2., 3., 4., 8.], [0., 0., 0., 0.]])
        expected = raw.copy()
        expected[0, 0] = 0
        r, good = profile_correlations(raw, [[0], [], []])
        self.assertEqual(good.tolist(), [True, True, False])
        self.assertAlmostEqual(r[0, 1], pearsonr(expected[0], expected[1]).statistic)
        self.assertTrue(np.isnan(r[0, 2]))
        self.assertEqual(raw[0, 0], 9.)

    def test_same_query_budgets_even_if_order_changes(self):
        rows = [{'pair_id': k, 'subject': a, 'object': b}
                for k, a, b in [('ab', 'a', 'b'), ('ac', 'a', 'c'), ('ad', 'a', 'd')]]
        a = top_neighbors(rows, ['ab', 'ac', 'ad'], {'a', 'b', 'c'}, 1)
        b = top_neighbors(rows, ['ad', 'ac', 'ab'], {'a', 'b', 'c'}, 1)
        self.assertEqual({k: len(v) for k, v in a.items()}, {k: len(v) for k, v in b.items()})
        self.assertEqual(a['a'], ['b'])
        self.assertEqual(b['a'], ['c'])

    def test_projection_does_not_admit_mixed_or_ambiguous_gene_products(self):
        def node(name, kind='ProteinReference', xref=None):
            return {'PARTICIPANT': name, 'PARTICIPANT_TYPE': kind,
                    'UNIFICATION_XREF': '', 'RELATIONSHIP_XREF': xref or 'hgnc symbol:' + name}
        nodes = [node('A'), node('B'), node('C', 'ProteinReference;DnaReference'),
                 node('D', xref='hgnc symbol:D;hgnc symbol:E')]
        edges = [{'PARTICIPANT_A': 'A', 'PARTICIPANT_B': b,
                  'INTERACTION_TYPE': kind} for b, kind in
                 [('B', 'in-complex-with'), ('C', 'in-complex-with'),
                  ('D', 'in-complex-with'), ('B', 'controls-state-change-of')]]
        pairs, eligible = complex_pairs(edges, nodes)
        self.assertEqual(set(pairs), {('A', 'B')})
        self.assertEqual(eligible, {'A', 'B'})

    def test_gene_assay_cannot_silently_choose_graph_protein(self):
        cols = ['status', 'locus_group', 'ensembl_gene_id', 'uniprot_ids', 'symbol', 'hgnc_id']
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'registry.tsv'
            with p.open('w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=cols, delimiter='\t'); w.writeheader()
                w.writerow(dict(zip(cols, ['Approved', 'protein-coding gene', 'ENSG1', 'P1|P2', 'A', 'HGNC:1'])))
                w.writerow(dict(zip(cols, ['Approved', 'protein-coding gene', 'ENSG2', 'P3', 'B', 'HGNC:2'])))
            mapping, excluded = gene_mapping(p, {'UniProtKB:P1', 'UniProtKB:P2', 'UniProtKB:P3'})
            self.assertEqual(set(mapping), {'UniProtKB:P3'})
            self.assertEqual(excluded['multiple_graph_proteins_for_gene'], 2)

    def test_paired_scores_preserve_zero_differences(self):
        result = paired_query_bootstrap({'a': .2, 'b': .4}, {'a': .1, 'b': .4}, ['a', 'b'], 7, 50)
        self.assertAlmostEqual(result['mean_difference'], .05)
        self.assertEqual(result['candidate_higher_queries'], 1)
        self.assertEqual(result['tied_queries'], 1)


if __name__ == '__main__':
    unittest.main()
