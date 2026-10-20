"""Invented source records only; no live APIs or biomedical gold judgments."""
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.cptac import inspect_matrix, load_cptac, prepare_cptac
from biograph_steward.crc_pilot import (build_tasks, load_pilot, prepare_pilot,
                                      retrieve_pilot_literature, run_pilot, verify_pilot_result)
from biograph_steward.crc_pilot import explicit_pmids
from biograph_steward.__main__ import main
from biograph_steward.graph import save_run
from biograph_steward.literature import (collect_literature, load_literature, parse_pmc,
                                        parse_pubmed, source_document)
from test_civic import fixture
from test_evaluation import cases


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


class FakeVerifier:
    kind = 'injected_test_model'
    model = 'INVENTED-SOFTWARE-TEST'
    def __init__(self, corrupt=False, bad_binding=False):
        self.calls = []; self.corrupt = corrupt; self.bad_binding = bad_binding
    def generate(self, prompt, schema, policy, audit):
        self.calls.append(prompt)
        task = json.loads(prompt.split('\nUntrusted input data:\n')[1])
        quote = task['document']['sentences'][0]['text'] + (' ALTERED' if self.corrupt else '')
        output = {'task_id': task['id'], 'verdict': 'SUPPORT',
                  'evidence': [{'sentence_index': 0, 'quote': quote}], 'reason_codes': [],
                  'explanation': 'INVENTED SOFTWARE TEST assessment, not science.',
                  'context_matches': [], 'context_mismatches': [], 'missing_details': [], 'follow_up': ''}
        trace = {**audit, 'status': 'completed', 'output': output, 'model_calls': 1}
        if self.bad_binding: trace['claim_sha256'] = 'changed'
        return trace


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

    def test_passage_window_retains_whole_text_and_never_claims_exhaustive_review(self):
        paper = {'title': 'TEST', 'abstract': [{'text': 'Original abstract.', 'locator': 'a', 'section': 'Abstract'}],
                 'full_text': [{'text': f'Whole paragraph {i}.', 'locator': str(i), 'section': 'Body'} for i in range(110)]}
        doc, selection = source_document(paper, 'paragraph 90', 'augmented')
        self.assertLessEqual(len(doc['sentences']), 90)
        self.assertFalse(selection['full_text_exhaustively_reviewed'])
        self.assertEqual(doc['sentences'][0]['text'], 'Original abstract.')
        originals = {p['text'] for p in paper['abstract'] + paper['full_text']}
        self.assertTrue(all(s['text'] in originals for s in doc['sentences']))


class CRCPilotTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True); env.start(); self.addCleanup(env.stop)
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.root = Path(tmp.name)
        p, c = fixture(); self.base = self.root / 'base'; self.enriched = self.root / 'enriched'
        save_run(p, self.base); self.graph = save_run(p, self.enriched, civic_snapshot=c)
        self.packet = self.root / 'packet'; self.lit = self.root / 'literature'

    def transport(self, url):
        if 'db=pubmed' in url:
            return pubmed_xml(url.split('id=')[-1].split(','))
        return jats_xml(url.split('id=')[-1])

    def prepare(self):
        p = prepare_pilot(self.base, self.enriched, self.packet, size=4, cases=cases())
        retrieve_pilot_literature(self.packet, self.lit, transport=self.transport)
        return p

    def test_preparation_reuses_sources_keeps_originals_and_leaves_science_unknown(self):
        before = (self.enriched / 'civic_snapshot.json').read_bytes()
        p = self.prepare(); loaded, panel, result = load_pilot(self.packet)
        self.assertEqual(p, loaded); self.assertEqual(len(panel), 4)
        self.assertEqual(before, (self.enriched / 'civic_snapshot.json').read_bytes())
        self.assertTrue(all(r['scientific_judgment'] is None for r in panel))
        self.assertTrue(all(o['trace'] is None for o in result['observations']))
        self.assertFalse(p['selection']['independent_or_unseen_test'])
        self.assertIn('g13d_focus_items', p['selection'])
        self.assertNotIn('previously_inspected_g13d_items_reused', p['selection'])
        with self.assertRaises(ValueError): prepare_pilot(self.base, self.enriched, self.packet, cases=cases())

    def test_offline_result_has_no_fabricated_verifier_success_and_escapes_source_html(self):
        self.prepare(); out = self.root / 'offline'
        with patch('biograph_steward.crc_pilot.configured_verifier', side_effect=AssertionError('No model')):
            r = run_pilot(self.packet, self.lit, out)
        self.assertEqual(r['model_requests'], 0); self.assertIsNone(r['scientific_accuracy'])
        self.assertEqual(r['views']['abstract']['machine_verdict_counts'], {})
        self.assertFalse(r['scientific_improvement_established']); verify_pilot_result(out)
        self.assertTrue(all(x['judgment'] is None for x in json.loads((out / 'scientific_reviews.json').read_text())))
        self.assertIn('Human scientific labels: zero', (out / 'report.html').read_text())

    def test_one_call_per_view_exact_quotes_and_no_judgments_in_model_input(self):
        self.prepare(); verifier = FakeVerifier(); out = self.root / 'assessed'
        r = run_pilot(self.packet, self.lit, out, mode='codex', verifier=verifier)
        self.assertEqual(r['model_requests'], 8); self.assertEqual(len(verifier.calls), 8)
        self.assertEqual(r['verifier_kind'], 'injected_test_model')
        self.assertEqual(r['views']['augmented']['machine_verdict_counts'], {'SUPPORT': 4})
        self.assertEqual(r['human_scientific_labels'], 0); self.assertIsNone(r['scientific_accuracy'])
        for prompt in verifier.calls:
            self.assertNotIn('scientific_judgment', prompt); self.assertNotIn('reference_plan', prompt)
        self.assertIn('&lt;script&gt;', (out / 'report.html').read_text())
        self.assertNotIn('<script>', (out / 'report.html').read_text()); verify_pilot_result(out)

    def test_invalid_quotes_or_wrong_input_binding_consume_case_without_repair(self):
        self.prepare()
        for name, verifier in [('quotes', FakeVerifier(corrupt=True)), ('bindings', FakeVerifier(bad_binding=True))]:
            out = self.root / name
            r = run_pilot(self.packet, self.lit, out, mode='codex', verifier=verifier)
            self.assertEqual(r['views']['abstract']['status_counts'], {'invalid_output': 4})
            self.assertEqual(len(verifier.calls), 8); self.assertEqual(r['model_requests'], 8)
            verify_pilot_result(out)

    def test_tampered_sources_fail_before_live_client_construction(self):
        self.prepare(); target = self.lit / 'papers.json'; target.write_bytes(target.read_bytes() + b'\n')
        with patch('biograph_steward.crc_pilot.configured_verifier') as factory:
            with self.assertRaisesRegex(ValueError, 'literature bytes changed'):
                run_pilot(self.packet, self.lit, self.root / 'bad', mode='codex')
            factory.assert_not_called()
        self.assertFalse((self.root / 'bad').exists())

    def test_missing_abstract_is_a_gap_and_can_still_use_available_body(self):
        self.prepare(); _, panel, _ = load_pilot(self.packet); _, papers = load_literature(self.lit)
        papers[panel[0]['pmid']]['abstract'] = []
        tasks, gaps = build_tasks(panel, papers)
        self.assertEqual(len(tasks), 7); self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]['reason'], 'no_bounded_source_text')
        self.assertTrue(any(e['item_id'] == panel[0]['item_id'] and e['view'] == 'augmented' for e in tasks))

    def test_completed_result_or_source_tampering_is_detected(self):
        self.prepare(); out = self.root / 'done'; verifier = FakeVerifier()
        run_pilot(self.packet, self.lit, out, mode='codex', verifier=verifier)
        raw = (out / 'assessments.json').read_bytes()
        with self.assertRaises(ValueError): run_pilot(self.packet, self.lit, out, mode='codex', verifier=verifier)
        self.assertEqual(len(verifier.calls), 8)
        (out / 'assessments.json').write_bytes(raw + b'\n')
        with self.assertRaises(ValueError): verify_pilot_result(out)

    def test_output_cannot_modify_input_or_historical_sources(self):
        with self.assertRaises(ValueError): prepare_pilot(self.base, self.enriched, self.base / 'child', cases=cases())
        self.assertFalse((self.base / 'child').exists())

    def test_cli_can_run_offline_without_model_configuration(self):
        self.prepare(); out = self.root / 'cli-offline'
        with redirect_stdout(StringIO()):
            self.assertEqual(main(['crc-pilot-run', '--packet', str(self.packet), '--literature', str(self.lit), '--out', str(out)]), 0)
        self.assertEqual(verify_pilot_result(out)['model_requests'], 0)

    def test_trace_edits_and_wrong_measurement_snapshot_are_detected(self):
        self.prepare(); out = self.root / 'traces'; run_pilot(self.packet, self.lit, out, mode='codex', verifier=FakeVerifier())
        trace = next((out / 'traces').glob('*.json')); trace.write_bytes(trace.read_bytes() + b'\n')
        with self.assertRaises(ValueError): verify_pilot_result(out)
        raw = b'attrib_name\tS1\tS2\nTEST_2\t0\tNA\n'; matrix = self.root / 'matrix.cct'; matrix.write_bytes(raw)
        cp = self.root / 'cptac'; r = prepare_cptac(self.base, cp, matrix=matrix)
        self.assertEqual(load_cptac(cp), r)
        r['pharos_snapshot_sha256'] = 'other'; r['sidecar_sha256'] = digest({k: v for k, v in r.items() if k != 'sidecar_sha256'})
        (cp / 'sidecar.json').write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError, 'another Pharos snapshot'):
            run_pilot(self.packet, self.lit, self.root / 'mismatched', cptac=cp)

    def test_explicit_citation_presence_does_not_invent_pmids_from_summary_counts(self):
        ids = explicit_pmids({'a': '2 PubMed IDs', 'pmid': 123, 'nested': ['PMID:456', 'https://pubmed.ncbi.nlm.nih.gov/789/']})
        self.assertEqual(ids, {'123', '456', '789'})


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


if __name__ == '__main__': unittest.main()
