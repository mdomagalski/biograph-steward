"""Invented source-contract fixtures; never biological reference labels."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from biograph_steward.client import digest, write_json
from biograph_steward.crc_pilot import prepare_pilot, retrieve_pilot_literature
from biograph_steward.evidence_quality import (prepare_quality, run_quality, verify_quality_result,
    load_quality_packet, quality_passports, POLICY, engine)
from biograph_steward.graph import save_run
from biograph_steward.webapp import create_server
from test_civic import fixture
from test_crc_pilot import pubmed_xml, jats_xml
from test_evaluation import cases as query_cases


class TestVerifier:
    kind = 'injected_test_model'
    model = 'INVENTED-SOFTWARE-TEST'
    def __init__(self, mode='correct'):
        self.mode = mode; self.calls = []
    def generate(self, prompt, schema, policy, audit):
        task = json.loads(prompt.split('\nUntrusted input data:\n')[1]); self.calls.append(task)
        verdict = 'SUPPORT'
        if self.mode == 'correct' and 'Altered' in task['claim']:
            verdict = 'NOT_ENOUGH_INFORMATION'
        if self.mode == 'fail':
            raise TimeoutError('Invented transport error')
        out = {'task_id': task['id'], 'verdict': verdict, 'reason_codes': [],
               'evidence': [] if verdict == 'NOT_ENOUGH_INFORMATION' else [
                   {'sentence_index': 0, 'quote': task['document']['sentences'][0]['text'] +
                    (' CHANGED' if self.mode == 'bad_quote' else '')}],
               'explanation': 'Invented fixture judgment only.', 'context_matches': [],
               'context_mismatches': [], 'missing_details': [], 'follow_up': ''}
        return {**audit, 'status': 'completed', 'output': out, 'model_calls': 1}


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); p, c = fixture()
        self.base = self.root / 'base'; self.enriched = self.root / 'enriched'
        save_run(p, self.base); self.graph = save_run(p, self.enriched, civic_snapshot=c)
        self.pilot = self.root / 'pilot'; self.lit = self.root / 'literature'
        prepare_pilot(self.base, self.enriched, self.pilot, size=4, cases=query_cases())
        def transport(url):
            if 'db=pubmed' in url:
                return pubmed_xml(url.split('id=')[-1].split(','))
            return jats_xml(url.split('id=')[-1])
        retrieve_pilot_literature(self.pilot, self.lit, transport=transport)
        self.specs = [{'id': 'invented', 'pmid': '90000100', 'passage_index': 0,
                       'claim': 'Invented fixture passage, not biological evidence.', 'changes': [
                           {'type': 'disease_context', 'before': 'Invented', 'after': 'Altered',
                            'reason': 'Invented source-contract edit, not biology.'},
                           {'type': 'negation', 'before': 'not biological', 'after': 'Altered biological',
                            'reason': 'Invented changed qualification.'}]}]
        self.packet = self.root / 'packet'
        prepare_quality(self.pilot, self.lit, self.packet, specs=self.specs)

    def test_exact_sources_and_references_are_frozen_without_changing_parent(self):
        before = (self.enriched / 'review_events.json').read_bytes()
        p, cs, refs, sources, contract = load_quality_packet(self.packet)
        self.assertEqual(p['cases'], 7); self.assertEqual(sum(r['expected'] is None for r in refs), 1)
        self.assertFalse(contract['graph_mutations']); self.assertEqual(contract['engine'], engine())
        self.assertEqual((self.enriched / 'review_events.json').read_bytes(), before)
        with self.assertRaises(ValueError): prepare_quality(self.pilot, self.lit, self.packet, specs=self.specs)
        altered = deepcopy(self.specs); altered[0]['claim'] = 'Nonexistent source sentence.'
        with self.assertRaisesRegex(ValueError, 'exact contiguous'):
            prepare_quality(self.pilot, self.lit, self.root / 'invalid', specs=altered)
        self.assertFalse((self.root / 'invalid').exists())

    def test_no_inference_mode_does_not_report_an_agent_comparison(self):
        with patch('biograph_steward.evidence_quality.configured_verifier', side_effect=AssertionError('No calls')):
            m = run_quality(self.packet, self.root / 'offline')
        self.assertEqual(m['model_requests'], 0); self.assertEqual(m['arms']['assisted']['status'], 'not_run')
        self.assertIsNone(m['arms']['assisted']['flag_precision'])
        self.assertEqual(m['arms']['original']['unsupported_test_cases_retained'], 5)
        self.assertEqual(m['arms']['deterministic']['unsupported_test_cases_retained'], 2)
        self.assertEqual(m['human_scientific_labels'], 0); self.assertIsNone(m['scientific_accuracy'])
        verify_quality_result(self.root / 'offline')

    def test_all_arms_same_inventory_references_hidden_and_no_lifecycle_mutations(self):
        verifier = TestVerifier(); out = self.root / 'result'
        original = {p.name: p.read_bytes() for p in self.enriched.iterdir() if p.is_file()}
        m = run_quality(self.packet, out, mode='api', verifier=verifier)
        self.assertEqual(len(verifier.calls), 4); self.assertEqual(m['model_requests'], 4)
        for task in verifier.calls:
            self.assertEqual(set(task), {'id', 'claim_id', 'document_id', 'claim', 'document'})
            self.assertRegex(task['id'], r'^task-[a-f0-9]{24}$')
            self.assertNotIn('expected', json.dumps(task)); self.assertNotIn('reference_kind', json.dumps(task))
        self.assertEqual(m['arms']['assisted']['supported_controls_retained'], 1)
        self.assertEqual(m['arms']['assisted']['unsupported_test_cases_retained'], 0)
        self.assertEqual(m['arms']['assisted']['flag_recall'], 1)
        self.assertEqual(m['arms']['assisted']['false_quarantine_rate'], 0)
        self.assertEqual(m['graph_mutations'], 0)
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.enriched.iterdir() if p.is_file()})
        self.assertEqual(verify_quality_result(out), m)
        for a in self.graph['assertions']:
            passports = quality_passports(out, self.graph, a['id'])
            self.assertTrue(all(p['case']['kind'] == 'original_annotation' for p in passports))

    def test_invalid_output_errors_and_false_support_remain_in_denominators(self):
        for mode in ['bad_quote', 'fail', 'accept']:
            v = TestVerifier(mode); m = run_quality(self.packet, self.root / mode, mode='api', verifier=v)
            self.assertEqual(len(v.calls), 4); self.assertEqual(m['model_requests'], 4)
            if mode == 'accept':
                self.assertEqual(m['arms']['assisted']['unsupported_test_cases_retained'], 2)
            else:
                self.assertEqual(m['arms']['assisted']['supported_controls_retained'], 0)
                self.assertEqual(m['arms']['assisted']['false_flag_rate'], 1)
                self.assertEqual(m['arms']['assisted']['false_quarantine_rate'], 0)
                self.assertEqual(m['decisive_assessments'], 0)
            verify_quality_result(self.root / mode)

    def test_tampered_packet_blocks_calls_and_changed_engine_requires_new_freeze(self):
        with patch('biograph_steward.evidence_quality.engine', return_value={}):
            with self.assertRaisesRegex(ValueError, 'engine changed'):
                run_quality(self.packet, self.root / 'changed')
        (self.packet / 'sources.json').write_text('{}')
        with patch('biograph_steward.evidence_quality.configured_verifier') as factory:
            with self.assertRaises(ValueError): run_quality(self.packet, self.root / 'bad', mode='api')
            factory.assert_not_called()
        self.assertFalse((self.root / 'bad').exists())

    def test_result_scores_traces_report_and_assertion_revision_are_checked(self):
        out = self.root / 'result'; m = run_quality(self.packet, out, mode='api', verifier=TestVerifier())
        c = json.loads((out / 'cases.json').read_text())[-1]
        self.assertEqual(len(quality_passports(out, self.graph, c['parent_assertion_id'])), 1)
        changed = deepcopy(self.graph); changed['civic_snapshot_sha256'] = 'other'
        self.assertEqual(quality_passports(out, changed, c['parent_assertion_id']), [])
        changed = deepcopy(self.graph)
        next(a for a in changed['assertions'] if a['id'] == c['parent_assertion_id'])['revision'] = 'other'
        self.assertEqual(quality_passports(out, changed, c['parent_assertion_id']), [])
        # Even a re-signed summary must match replayed observations.
        mutated = deepcopy(m); mutated['arms']['original']['flag_recall'] = 1
        mutated.pop('result_sha256'); mutated['result_sha256'] = digest(mutated)
        write_json(out / 'metrics.json', mutated)
        with self.assertRaisesRegex(ValueError, 'metrics do not replay'): verify_quality_result(out)
        write_json(out / 'metrics.json', m)
        (out / 'report.html').write_text('<script>changed</script>')
        with self.assertRaisesRegex(ValueError, 'report changed'): verify_quality_result(out)

    def test_http_passports_are_authenticated_read_only_and_synthetic_edits_excluded(self):
        out = self.root / 'quality_result'; run_quality(self.packet, out, mode='api', verifier=TestVerifier())
        token = 'invented-test-token-000000000000'
        server = create_server(0, self.root, access_token=token)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:' + str(server.server_port)
        http = build_opener(ProxyHandler({}))
        with self.assertRaises(HTTPError) as error: http.open(url + '/api/evidence-quality')
        self.assertEqual(error.exception.code, 401)
        def get(path):
            with http.open(Request(url + path, headers={'Authorization': 'Bearer ' + token})) as response:
                return json.loads(response.read())
        self.assertEqual(len(get('/api/evidence-quality')['reports']), 1)
        c = json.loads((out / 'cases.json').read_text())[-1]
        data = get('/api/evidence-quality?run=enriched&assertion=' + c['parent_assertion_id'])
        self.assertEqual(len(data['passports']), 1)
        self.assertEqual(data['passports'][0]['case']['kind'], 'original_annotation')
        self.assertEqual(data['graph_mutations'], 0)
        with self.assertRaises(HTTPError): get('/api/evidence-quality?run=../outside&assertion=x')
        with http.open(Request(url, headers={'Authorization': 'Bearer ' + token})) as response:
            html = response.read().decode()
        self.assertIn('Evidence-quality comparison', html)
        self.assertIn('appendQualityFindings(a', html)
        self.assertNotIn('__GUIDED_SCRIPT__', html)
        (out / 'report.html').write_text('changed report')
        for path in ['/api/evaluation/quality_result/', '/api/download/quality_result']:
            with self.assertRaises(HTTPError) as error: get(path)
            self.assertEqual(error.exception.code, 400)
        self.assertEqual(get('/api/evidence-quality')['invalid_reports_withheld'], 1)


if __name__ == '__main__': unittest.main()
