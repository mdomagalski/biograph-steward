"""Retained public-source adapters; invented fixtures, no live APIs or gold labels."""
from copy import deepcopy
import unittest
from biograph_steward.cptac import inspect_matrix
from biograph_steward.literature import parse_pmc, parse_pubmed
from test_civic import fixture


def pubmed_xml(pmids):
    records = ''.join('<PubmedArticle><MedlineCitation><PMID>' + p + '</PMID><Article>'
        '<ArticleTitle>INVENTED &lt;script&gt; title</ArticleTitle><Abstract><AbstractText Label="RESULTS">'
        'Invented fixture passage, not biological evidence.</AbstractText></Abstract></Article></MedlineCitation>'
        '<PubmedData><ArticleIdList><ArticleId IdType="pmc">PMC' + p + '</ArticleId></ArticleIdList></PubmedData>'
        '</PubmedArticle>' for p in pmids)
    return ('<PubmedArticleSet>' + records + '</PubmedArticleSet>').encode()


def jats_xml(pmid):
    return ('<article><front><article-meta><article-id pub-id-type="pmid">' + pmid +
            '</article-id><permissions><license>INVENTED TEST LICENSE</license></permissions></article-meta></front>'
            '<body><sec><title>Results</title><p>Another invented source passage. No scientific result.</p>'
            '<table-wrap><caption>Invented table</caption><table><tr><td>TEST</td></tr></table></table-wrap>'
            '</sec></body></article>').encode()


class SourceTests(unittest.TestCase):
    def test_pubmed_preserves_identity_structured_text_and_missing_abstracts(self):
        xml = pubmed_xml(['123']).replace(b'<Abstract><AbstractText Label="RESULTS">', b'<Abstract><AbstractText Label="RESULTS">')
        r = parse_pubmed(xml)['123']
        self.assertEqual(r['pmcid'], 'PMC123'); self.assertEqual(r['abstract'][0]['section'], 'RESULTS')
        self.assertIn('AbstractText[1]', r['abstract'][0]['locator'])
        self.assertEqual(parse_pubmed(b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID></MedlineCitation></PubmedArticle></PubmedArticleSet>')['123']['abstract'], [])
        with self.assertRaises(ValueError): parse_pubmed(b'<Wrong/>')
        with self.assertRaises(ValueError): parse_pubmed(b'<malformed')
        with self.assertRaises(ValueError): parse_pubmed(pubmed_xml(['123', '123']))

    def test_full_text_requires_matching_identity_and_preserves_table_locators(self):
        r = parse_pmc(jats_xml('123'), '123', 'PMC123')
        self.assertEqual(len(r['passages']), 2)
        self.assertIn('table-wrap[1]', r['passages'][1]['locator'])
        self.assertEqual(r['license'], ['INVENTED TEST LICENSE'])
        with self.assertRaises(ValueError): parse_pmc(jats_xml('456'), '123', 'PMC123')
        with self.assertRaises(ValueError): parse_pmc(b'<malformed', '123', 'PMC123')



class CPTACTests(unittest.TestCase):
    def setUp(self):
        p, c = fixture(); from biograph_steward.graph import build_graph
        self.graph = build_graph(p, civic_snapshot=c)

    def test_missing_is_not_zero_and_exact_gene_mapping_preserves_original_measurements(self):
        raw = b'attrib_name\tS1\tS2\nTEST_2\t0\tNA\nUNLISTED\t-2\t3\n'
        r = inspect_matrix(raw, self.graph)
        self.assertEqual(r['gene_rows'], 2); self.assertEqual(r['sample_columns'], 2)
        self.assertEqual(r['missing_values'], 1); self.assertEqual(r['observed_values'], 3)
        self.assertEqual(r['matched_measurements'][0]['median_reported_log2_ratio'], 0)
        self.assertEqual(r['matched_measurements'][0]['nonmissing_samples'], 1)
        self.assertEqual(r['labels_created'], 0); self.assertEqual(r['graph_assertions_created'], 0)

    def test_malformed_duplicate_and_nonfinite_matrices_are_rejected(self):
        for raw in [b'attrib_name\tS1\tS1\nKRAS\t0\t1\n', b'attrib_name\tS1\tS2\nKRAS\t1\n',
                    b'attrib_name\tS1\tS2\nKRAS\t0\t1\nKRAS\t2\t3\n', b'attrib_name\tS1\tS2\nKRAS\tinf\t1\n']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError): inspect_matrix(raw, self.graph)

    def test_ambiguous_cohort_symbols_are_not_silently_resolved(self):
        g = deepcopy(self.graph); g['nodes'].append({'id': 'UniProtKB:INVENTED', 'sym': 'TEST_2'})
        r = inspect_matrix(b'attrib_name\tS1\tS2\nTEST_2\t1\t2\n', g)
        self.assertEqual(r['matched_measurements'][0]['mapping_status'], 'ambiguous_cohort_symbol')
