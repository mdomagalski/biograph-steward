"""Invented data tests of input boundaries and native numerical execution."""
import json
from pathlib import Path
import tempfile
import unittest

from .core import graph_frame, ontology_terms, training_annotations


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.nodes = self.root / 'nodes.tsv'
        self.nodes.write_text('node_id\tcanonical_graph_node_present\nUniProtKB:A1\ttrue\nUniProtKB:B2\ttrue\nUniProtKB:C3\tfalse\n')
        self.pairs = self.root / 'pairs.tsv'
        self.pairs.write_text('subject\tobject\tweight\tpair_id\nUniProtKB:A1\tUniProtKB:B2\t0.4\tone\n')

    def test_absent_lookup_not_a_node_or_zero_weight_edge(self):
        nodes, pairs = graph_frame(self.nodes, self.pairs)
        self.assertEqual(nodes, ['UniProtKB:A1', 'UniProtKB:B2'])
        self.assertEqual(pairs, [('UniProtKB:A1', 'UniProtKB:B2', .4)])
        for weight in ('', 'nan', 'inf', '0', '-.1', '1.1'):
            with self.subTest(weight=weight), self.assertRaises(ValueError):
                self.pairs.write_text('subject\tobject\tweight\tpair_id\nUniProtKB:A1\tUniProtKB:B2\t' + weight + '\tone\n')
                graph_frame(self.nodes, self.pairs)

    def test_duplicate_or_outside_graph_pair_rejected(self):
        self.pairs.write_text(self.pairs.read_text() + 'UniProtKB:B2\tUniProtKB:A1\t0.4\ttwo\n')
        with self.assertRaisesRegex(ValueError, 'duplicate'): graph_frame(self.nodes, self.pairs)
        self.pairs.write_text('subject\tobject\tweight\tpair_id\nUniProtKB:A1\tUniProtKB:C3\t0.4\tone\n')
        with self.assertRaisesRegex(ValueError, 'outside'): graph_frame(self.nodes, self.pairs)

    def test_t0_header_duplicates_aspect_denominator_and_unknown_do_not_become_negatives(self):
        known = self.root / 'known.tsv'
        known.write_text('EntryID\tterm\taspect\nA1\tGO:0000001\tBPO\nA1\tGO:0000001\tBPO\nB2\tGO:0000002\tMFO\nD4\tGO:0000001\tBPO\nD4\tGO:0000003\tBPO\n')
        labels, frequencies, counts = training_annotations(known, ['UniProtKB:A1', 'UniProtKB:B2', 'UniProtKB:E5'],
            {'GO:0000001': 'biological_process', 'GO:0000002': 'molecular_function', 'GO:0000003': 'biological_process'})
        self.assertEqual(labels['E5'], set())
        self.assertEqual(labels['A1'], {('BPO', 'GO:0000001')})
        self.assertEqual(frequencies['BPO'], {'GO:0000001': 1, 'GO:0000003': .5})
        self.assertEqual(frequencies['MFO']['GO:0000002'], 1)
        self.assertEqual(counts['source_proteins'], 3)
        self.assertEqual(counts['duplicate_rows_collapsed'], 1)
        self.assertFalse(counts['future_GO_labels_read'])

    def test_t0_order_is_irrelevant_and_aspect_mismatch_is_explicit(self):
        known = self.root / 'known.tsv'
        known.write_text('EntryID\tterm\taspect\nB2\tGO:0000001\tBPO\nA1\tGO:0000001\tBPO\n')
        labels, frequencies, counts = training_annotations(known, ['UniProtKB:A1'], {'GO:0000001': 'biological_process'})
        self.assertEqual(labels['A1'], {('BPO', 'GO:0000001')})
        self.assertEqual(frequencies['BPO']['GO:0000001'], 1)
        known.write_text('EntryID\tterm\taspect\nA1\tGO:0000001\tMFO\n')
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            training_annotations(known, ['UniProtKB:A1'], {'GO:0000001': 'biological_process'})

    def test_frozen_ontology_keeps_namespaces_and_excludes_obsoletes(self):
        path = self.root / 'go.obo'
        path.write_text('format-version: 1.2\n[Term]\nid: GO:0000001\nnamespace: biological_process\n[Term]\nid: GO:0000002\nnamespace: molecular_function\nis_obsolete: true\n[Typedef]\nid: regulates\n')
        self.assertEqual(ontology_terms(path), {'GO:0000001': 'biological_process'})


class AuthorExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
            import scipy
            from .core import RUNTIME
            from importlib import metadata
            if any(metadata.version(k) != v for k, v in RUNTIME.items()):
                raise unittest.SkipTest('optional pinned numerical runtime unavailable')
        except ImportError:
            raise unittest.SkipTest('optional numerical runtime unavailable')
        directory = Path('runs/prediction_next_20261113/author_methods')
        receipt = directory.parent / 'author_methods_receipt.json'
        if not receipt.exists(): raise unittest.SkipTest('optional separately licensed author code unavailable')
        from .core import author_modules
        cls.modules = author_modules(directory, receipt)

    def test_author_methods_match_independent_small_linear_solutions_and_preserve_isolate(self):
        import numpy as np
        from .core import adjacency, run_term
        W = adjacency(['A', 'B', 'C', 'D'], [('A', 'B', .6), ('B', 'C', .3)])
        with np.errstate(divide='ignore'):
            P = self.modules['alg_utils'].normalizeGraphEdgeWeights(W)
            L = self.modules['gm'].setup_laplacian(W)
        scores, _ = run_term(self.modules, P, L, [0], 'localplus')
        np.testing.assert_allclose(scores, [0, 2/3, 0, 0], atol=1e-15)
        ss, diag = run_term(self.modules, P, L, [0], 'fastsinksourceplus')
        # Unknown B/C solve s=.8*P*s, with A fixed at 1; isolated D stays 0.
        p = P.toarray(); expected = np.zeros(4); expected[0] = 1
        expected[1:] = np.linalg.solve(np.eye(3) - .8*p[1:,1:], .8*p[1:,0])
        np.testing.assert_allclose(ss, expected, atol=.0005)
        self.assertEqual(ss[3], 0)
        gm, diag = run_term(self.modules, P, L, [0], 'genemaniaplus')
        np.testing.assert_allclose(gm, np.linalg.solve(np.eye(4)+L.toarray(), [1,0,0,0]), atol=1e-12)
        self.assertEqual(gm[3], 0)

    def test_all_positive_boundary_and_unknown_method(self):
        import numpy as np
        from .core import adjacency, run_term
        W = adjacency(['A', 'B'], [('A', 'B', .6)])
        P = self.modules['alg_utils'].normalizeGraphEdgeWeights(W)
        L = self.modules['gm'].setup_laplacian(W)
        scores, _ = run_term(self.modules, P, L, [0,1], 'fastsinksourceplus')
        np.testing.assert_array_equal(scores, [1,1])
        with self.assertRaises(ValueError): run_term(self.modules,P,L,[0],'invented')


if __name__ == '__main__': unittest.main()
