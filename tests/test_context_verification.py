"""Invented software fixtures; no biomedical reference judgments."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

from biograph_steward.client import digest
from biograph_steward.context_verification import (AXES, schema, validate, eligibility,
    literal_checks, verify_context, wire_schema, bind_wire)
from biograph_steward.context_evaluation import (prepare_context, run_context,
    verify_context_result, load_packet)
from biograph_steward.evidence_quality import verify_quality_result
from biograph_steward.literature import collect_literature
from biograph_steward.webapp import create_server


def task(claim='Invented signal is reported.', source='Invented observation reports a signal.'):
    return {'id': 'invented', 'claim_id': 1, 'document_id': 90000101, 'claim': claim,
            'document': {'title': 'INVENTED', 'sentences': [{'index': 0, 'text': source}]}}


def output(t):
    return {'task_id': t['id'], 'verdict': 'SUPPORT', 'evidence': [0],
            'explanation': 'Invented fixture only.', 'context': {a: {
                'relation': 'not_asserted', 'claim_span': '', 'source_span': '', 'index': -1} for a in AXES}}


class Fake:
    kind = 'injected_test_model'; model = 'INVENTED'
    def __init__(self, mode='correct'): self.mode = mode; self.calls = []
    def generate(self, prompt, definition, policy, audit):
        t = json.loads(prompt.split('\nUntrusted input data:\n')[1]); self.calls.append(t)
        if self.mode == 'error': raise TimeoutError('PRIVATE')
        if 'context' in definition['properties']:
            o = output(t)
            if 'altered' in t['claim']:
                o['verdict'] = 'NOT_ENOUGH_INFORMATION'
                o['context']['qualification'] = {'relation': 'mismatch', 'claim_span': 'altered',
                    'source_span': 'Invented', 'index': 0}
            if self.mode == 'duplicate': o['evidence'] = [0, 0]
            if definition['properties']['evidence']['type'] == 'object':
                o['evidence'] = {str(i): i == 0 for i in range(len(t['document']['sentences']))}
                if self.mode == 'duplicate': o['evidence']['extra'] = True
        else:
            o = {'task_id': t['id'], 'verdict': 'NOT_ENOUGH_INFORMATION' if 'altered' in t['claim'] else 'SUPPORT',
                 'evidence': [] if 'altered' in t['claim'] else [{'sentence_index': 0}],
                 'explanation': 'Invented fixture only.', 'reason_codes': [], 'context_matches': [],
                 'context_mismatches': [], 'missing_details': [], 'follow_up': ''}
        return {**audit, 'status': 'completed', 'output': o, 'schema_sha256': digest(definition), 'model_calls': 1}


class ContextTests(unittest.TestCase):
    def test_unique_bounded_citations_and_exact_spans_are_locally_enforced(self):
        t = task(); o = output(t); validate(o, t)
        s = schema(t); self.assertTrue(s['properties']['evidence']['uniqueItems'])
        self.assertEqual(s['properties']['evidence']['maxItems'], 1)
        self.assertEqual(s['properties']['task_id']['enum'], ['invented'])
        for bad in ([0, 0], [True], [-1], [1]):
            x = deepcopy(o); x['evidence'] = bad
            with self.assertRaises(ValueError): validate(x, t)
        for change in ({'source_span': 'NOT IN SOURCE', 'index': 0},
                       {'claim_span': 'NOT IN CLAIM'}, {'index': True}):
            x = deepcopy(o); x['context']['disease'].update(change)
            with self.assertRaises(ValueError): validate(x, t)
        x = deepcopy(o); x['explanation'] = 'x' * 301
        with self.assertRaises(ValueError): validate(x, t)

    def test_known_missing_literals_and_omitted_claim_context_withhold_support(self):
        t = task('Invented pancreatic cancer with KRAS G12D.', 'Invented colorectal cancer with KRAS G12C.')
        g = eligibility(t, output(t)); self.assertFalse(g['support_eligible'])
        self.assertEqual(g['action'], 'request_review'); self.assertEqual(g['graph_mutations'], 0)
        self.assertTrue(any(r['literal'] == 'G12D' and not r['source_hits'] for r in g['literal_checks']))
        self.assertTrue(any(f['code'] == 'claim_context_omitted' for f in g['findings']))

    def test_grounded_context_match_and_verdict_disagreement_are_separate(self):
        t = task('Invented colorectal outcome.', 'Invented colorectal result.')
        o = output(t); o['context']['disease'] = {'relation': 'match', 'claim_span': 'colorectal',
                                                'source_span': 'colorectal', 'index': 0}
        self.assertTrue(eligibility(t, o)['support_eligible'])
        o['context']['disease']['relation'] = 'unknown'
        g = eligibility(t, o); self.assertFalse(g['support_eligible'])
        self.assertIn('verdict_context_disagreement', [f['code'] for f in g['findings']])
        # Literal co-occurrence alone must never be advertised as entailment.
        self.assertEqual(literal_checks(t)[0]['status'], 'present_not_entailment')

    def test_citation_or_span_failure_is_not_repaired(self):
        trace = verify_context(task(), Fake('duplicate'))
        self.assertEqual(trace['status'], 'invalid_output'); self.assertIsNone(trace['assessment'])
        self.assertIn('extra', trace['raw_output']['evidence'])
        self.assertFalse(trace['gate']['support_eligible'])

    def test_native_wire_map_is_unique_and_bounds_remain_mandatory_locally(self):
        t = task(); definition = wire_schema(t)
        self.assertEqual(definition['properties']['evidence']['required'], ['0'])
        self.assertNotIn('maxLength', json.dumps(definition))
        raw = output(t); raw['evidence'] = {'0': True}
        self.assertEqual(bind_wire(t, raw)['evidence'], [0])
        raw['explanation'] = 'x' * 301
        with self.assertRaises(ValueError): bind_wire(t, raw)
        raw = output(t); raw['evidence'] = {'0': 1}
        with self.assertRaises(ValueError): bind_wire(t, raw)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        def transport(url):
            ids = url.split('id=')[-1].split(',')
            return ('<PubmedArticleSet>' + ''.join('<PubmedArticle><MedlineCitation><PMID>' + p +
                '</PMID><Article><ArticleTitle>INVENTED</ArticleTitle><Abstract><AbstractText>'
                'Invented observation reports a signal.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle>'
                for p in ids) + '</PubmedArticleSet>').encode()
        self.fresh = self.root / 'fresh'; self.prior = self.root / 'prior'
        collect_literature(['90000101'], self.fresh, transport=transport)
        collect_literature(['90000000'], self.prior, transport=transport)
        specs = [{'id': 'invented-positive', 'pmid': '90000101', 'kind': 'paraphrase',
                  'claim': 'Invented signal is reported.', 'expected': 'SUPPORT', 'axis': None,
                  'rationale_sets': [[0]], 'reason': 'Invented software control.'},
                 {'id': 'invented-negative', 'pmid': '90000101', 'kind': 'context_edit',
                  'claim': 'Invented altered signal is reported.', 'expected': 'NOT_ENOUGH_INFORMATION',
                  'axis': 'qualification', 'rationale_sets': [[0]], 'reason': 'Invented edit.'}]
        self.packet = self.root / 'packet'; self.specs = specs
        prepare_context(self.fresh, [self.prior], self.packet, specs=specs)

    def test_fresh_exclusion_gold_hidden_closed_predictions_and_replay(self):
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            prepare_context(self.fresh, [self.fresh], self.root / 'overlap', specs=self.specs)
        self.assertFalse((self.root / 'overlap').exists())
        fake = Fake(); out = self.root / 'live'
        import biograph_steward.context_evaluation as module
        original = module.read
        def guarded(p):
            if Path(p) == out / 'references.json':
                self.assertEqual(len(fake.calls), 4)
                self.assertEqual(original(out / 'execution.json')['status'], 'predictions_closed')
            return original(p)
        with patch.object(module, 'read', side_effect=guarded):
            m = run_context(self.packet, out, mode='api', verifier=fake)
        self.assertEqual(m['model_requests'], 4)
        self.assertEqual(m['arms']['context_checked']['supported_controls_retained'], 1)
        self.assertEqual(m['arms']['context_checked']['context_errors_retained'], 0)
        self.assertEqual(m['outputs']['context_v3']['expected_context_axis_aligned'], 1)
        for t in fake.calls:
            self.assertEqual(set(t), {'id', 'claim_id', 'document_id', 'claim', 'document'})
            self.assertNotIn('expected', json.dumps(t))
        self.assertEqual(verify_context_result(out), m)
        with self.assertRaises(ValueError): run_context(self.packet, out)

    def test_errors_stay_in_denominators_and_no_inference_is_explicit(self):
        m = run_context(self.packet, self.root / 'error', mode='api', verifier=Fake('error'))
        self.assertEqual(m['model_requests'], 4)
        self.assertEqual(m['outputs']['context_v3']['reference_verdict_match_rate_all_cases'], 0)
        self.assertEqual(m['arms']['context_checked']['false_flags'], 1)
        self.assertEqual(m['human_rationale_labels'], 0)
        with patch('biograph_steward.context_evaluation.configured_verifier', side_effect=AssertionError('No calls')):
            m = run_context(self.packet, self.root / 'none')
        self.assertEqual(m['model_requests'], 0); self.assertEqual(m['arms']['context_checked'], {'status': 'not_run'})

    def test_changed_sources_or_engine_block_before_calls_and_tamper_blocks_replay(self):
        with patch('biograph_steward.context_evaluation.engine', return_value={}):
            with self.assertRaisesRegex(ValueError, 'engine changed'):
                run_context(self.packet, self.root / 'changed', mode='api', verifier=Fake())
        m = run_context(self.packet, self.root / 'result', mode='api', verifier=Fake())
        p = next((self.root / 'result' / 'traces').glob('*')); p.write_text('{}')
        with self.assertRaises(ValueError): verify_context_result(self.root / 'result')
        (self.packet / 'literature/papers.json').write_text('[]')
        fake = Fake()
        with self.assertRaises(ValueError): run_context(self.packet, self.root / 'bad', mode='api', verifier=fake)
        self.assertFalse(fake.calls); self.assertFalse((self.root / 'bad').exists())

    def test_new_reports_are_protected_listed_and_integrity_checked(self):
        runs = self.root / 'runs'; runs.mkdir(); out = runs / 'context_report'
        run_context(self.packet, out, mode='api', verifier=Fake())
        token = 'invented-test-token-000000000000'
        server = create_server(port=0, runs_dir=runs, access_token=token)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        from urllib.request import Request
        opener = build_opener(ProxyHandler({})); base = 'http://127.0.0.1:' + str(server.server_port)
        def get(path, auth=True):
            return opener.open(Request(base + path, headers={'Authorization': 'Bearer ' + token} if auth else {}))
        with self.assertRaises(HTTPError) as caught: get('/api/evaluation/context_report/', auth=False)
        self.assertIn(caught.exception.code, (401, 403)); caught.exception.close()
        with get('/api/evidence-quality') as r: self.assertEqual(len(json.load(r)['reports']), 1)
        with get('/api/evaluation/context_report/') as r: self.assertIn(b'Context verification comparison', r.read())
        (out / 'report.html').write_text('ALTERED')
        for path in ('/api/evaluation/context_report/', '/api/download/context_report'):
            with self.assertRaises(HTTPError) as caught: get(path)
            self.assertEqual(caught.exception.code, 400); caught.exception.close()


if __name__ == '__main__': unittest.main()
