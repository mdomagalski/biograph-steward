"""Invented source tasks; no invented biomedical gold or live model calls."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.verification import (CodexVerifier, VerificationOutputError, baseline_verdict,
                                           binding, validate_task, validate_verdict)
from biograph_steward.verification_evaluation import (file_sha, read_rows, run_verification,
                                                      rescore_verification, score_predictions, write_rows)
from test_codex_planner import events


def task(i=1):
    return {'id': f'INVENTED.{i}', 'claim_id': i, 'document_id': i,
            'claim': 'INVENTED blue boxes contain circles.',
            'document': {'title': 'INVENTED software test source', 'sentences': [
                {'index': 0, 'text': 'INVENTED blue boxes were studied.'},
                {'index': 1, 'text': 'INVENTED boxes contained circles.'},
                {'index': 2, 'text': 'INVENTED alternative complete sentence.'}]}}


def verdict(t, label='SUPPORT', indices=(0, 1)):
    v = baseline_verdict(t, 'always_insufficient')
    v.update(verdict=label, evidence=[{'sentence_index': i, 'quote': t['document']['sentences'][i]['text']} for i in indices])
    return v


def prediction(t, v=None, status='validated', bad=0):
    return {'id': t['id'], **binding(t), 'status': status, 'verdict': v, 'invalid_references': bad}


class VerdictTests(unittest.TestCase):
    def test_exact_sentences_identity_and_budget_required(self):
        t = task(); v = verdict(t)
        self.assertEqual(validate_verdict(v, t), v)
        bad = []
        a = copy.deepcopy(v); a['task_id'] = 'other'; bad.append(a)
        a = copy.deepcopy(v); a['evidence'][0]['quote'] += ' altered'; bad.append(a)
        a = copy.deepcopy(v); a['evidence'][0]['sentence_index'] = True; bad.append(a)
        a = copy.deepcopy(v); a['evidence'][0]['sentence_index'] = 99; bad.append(a)
        a = copy.deepcopy(v); a['evidence'].append(a['evidence'][0]); bad.append(a)
        a = copy.deepcopy(v); a['evidence'] *= 2; bad.append(a)
        a = copy.deepcopy(v); a['evidence'] = []; bad.append(a)
        a = copy.deepcopy(v); a['extra'] = 'not permitted'; bad.append(a)
        a = copy.deepcopy(v); a['reason_codes'] = ['invented_reason']; bad.append(a)
        a = copy.deepcopy(v); a['context_matches'] = [['nested']]; bad.append(a)
        for output in bad:
            with self.subTest(output=output), self.assertRaises(VerificationOutputError):
                validate_verdict(output, t)
        self.assertEqual(validate_verdict(verdict(t, 'NOT_ENOUGH_INFORMATION', ()), t)['evidence'], [])
        with self.assertRaises(VerificationOutputError):
            validate_verdict(verdict(t, 'NOT_ENOUGH_INFORMATION'), t)

    def test_task_allowlist_rejects_gold_and_noncontiguous_source(self):
        t = task(); self.assertEqual(validate_task(t), t)
        for mutate in [lambda x: x.update(label='SUPPORT'),
                       lambda x: x['document'].update(rationale=[0]),
                       lambda x: x['document']['sentences'][0].update(index=4)]:
            a = copy.deepcopy(t); mutate(a)
            with self.assertRaises(ValueError): validate_task(a)

    def test_cli_verifier_prompt_only_task_and_exact_output_validation(self):
        t = task(); calls = []
        def runner(args, **kwargs):
            if args[-1] == '--version': return subprocess.CompletedProcess(args, 0, 'codex-cli 1.2.3', '')
            calls.append(kwargs)
            self.assertEqual(sorted(p.name for p in Path(args[args.index('--cd') + 1]).iterdir()), ['schema.json'])
            Path(args[args.index('--output-last-message') + 1]).write_text(json.dumps(verdict(t)))
            return subprocess.CompletedProcess(args, 0, '\n'.join(json.dumps(e) for e in events()), 'PRIVATE STDERR')
        with patch('biograph_steward.codex_transport.shutil.which', return_value='/test/codex'):
            trace = CodexVerifier(model='test', runner=runner).verify(t)
        self.assertEqual(trace['status'], 'validated'); self.assertEqual(trace['task_sha256'], digest(t))
        supplied = json.loads(calls[0]['input'].split('Untrusted input data:\n')[1])
        self.assertEqual(supplied, t)
        self.assertNotIn('PRIVATE', json.dumps(trace)); self.assertEqual(trace['model_calls'], 1)

    def test_baselines_fixed_no_false_contradiction_from_absence(self):
        t = task(); t['claim'] = 'Unrelated invented topic absent entirely.'
        for mode in ['accept_all', 'always_insufficient', 'lexical_overlap']:
            v = validate_verdict(baseline_verdict(t, mode), t)
            self.assertNotEqual(v['verdict'], 'CONTRADICT')
        self.assertEqual(baseline_verdict(t, 'lexical_overlap')['verdict'], 'NOT_ENOUGH_INFORMATION')


class ScorerTests(unittest.TestCase):
    def test_whole_alternative_rationale_required_and_label_sensitive_sentence_counts(self):
        t = task(); g = [{'id': t['id'], 'label': 'SUPPORT', 'rationale_sets': [[0, 1], [2]]}]
        partial = score_predictions([t], g, [prediction(t, verdict(t, indices=(0,)))])
        self.assertEqual(partial['accuracy'], 1); self.assertEqual(partial['complete_rationale_coverage'], 0)
        self.assertEqual(partial['evidence_sentence_precision'], 0)
        alternate = score_predictions([t], g, [prediction(t, verdict(t, indices=(2,)))])
        self.assertEqual(alternate['complete_rationale_coverage'], 1)
        self.assertEqual(alternate['evidence_sentence_precision'], 1)
        self.assertEqual(alternate['evidence_sentence_recall'], 1/3)
        wrong_label = score_predictions([t], g, [prediction(t, verdict(t, 'CONTRADICT', (0, 1)))])
        self.assertEqual(wrong_label['complete_rationale_coverage'], 1)
        self.assertEqual(wrong_label['label_and_complete_rationale_accuracy'], 0)
        self.assertEqual(wrong_label['evidence_sentence_precision'], 0)

    def test_errors_and_false_support_in_denominators(self):
        tasks = [task(i) for i in range(3)]
        gold = [{'id': t['id'], 'label': label, 'rationale_sets': [] if label.endswith('INFORMATION') else [[0, 1]]}
                for t, label in zip(tasks, ['SUPPORT', 'CONTRADICT', 'NOT_ENOUGH_INFORMATION'])]
        predictions = [prediction(tasks[0], verdict(tasks[0])), prediction(tasks[1], verdict(tasks[1])),
                       prediction(tasks[2], status='invalid_output', bad=1)]
        m = score_predictions(tasks, gold, predictions)
        self.assertEqual(m['accuracy'], 1/3); self.assertEqual(m['error_rate'], 1/3)
        self.assertEqual(m['false_support_rate'], .5); self.assertEqual(m['support_precision'], .5)
        self.assertEqual(m['per_class']['NOT_ENOUGH_INFORMATION']['false_negative'], 1)
        self.assertEqual(m['invalid_reference_rate'], 1/3)
        self.assertAlmostEqual(m['macro_f1'], (2/3)/3)
        predictions[0]['document_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'binding'): score_predictions(tasks, gold, predictions)

    def test_duplicate_missing_or_invalid_gold_not_silently_scored(self):
        t = task(); g = [{'id': t['id'], 'label': 'SUPPORT', 'rationale_sets': [[0]]}]
        p = prediction(t, verdict(t))
        for predictions in [[], [p, p]]:
            with self.assertRaises(ValueError): score_predictions([t], g, predictions)
        for rationales in [[], [[99]], [[True]], [[0, 0]]]:
            with self.assertRaises(ValueError):
                score_predictions([t], [{**g[0], 'rationale_sets': rationales}], [p])


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.benchmark = self.root / 'benchmark'; self.benchmark.mkdir()
        self.tasks = [task(i) for i in range(1, 5)]
        self.gold = [{'id': t['id'], 'label': 'SUPPORT', 'rationale_sets': [[0, 1]]} for t in self.tasks]
        write_rows(self.benchmark/'inputs.jsonl', self.tasks); write_rows(self.benchmark/'gold.jsonl', self.gold)
        manifest = {'format': 'biograph-steward.provided-document-verification.v1', 'claim_abstract_pairs': 4,
                    'inputs_sha256': file_sha(self.benchmark/'inputs.jsonl'), 'gold_sha256': file_sha(self.benchmark/'gold.jsonl')}
        (self.benchmark/'manifest.json').write_text(json.dumps(manifest))

    def fake_verifier(self):
        class Fake:
            model = 'invented-test-model'; kind = 'injected_test_model'
            def verify(inner, t):
                return {**binding(t), 'status': 'validated', 'verdict': verdict(t), 'model_calls': 1}
        return Fake()

    def test_labels_parsed_only_after_predictions_close_and_no_writes_to_sources(self):
        import biograph_steward.verification_evaluation as module
        out = self.root/'result'; original = file_sha(self.benchmark/'gold.jsonl')
        calls = []; fake = self.fake_verifier(); verify = fake.verify
        def record(t):
            self.assertFalse((out/'gold.jsonl').exists()); calls.append(t['id']); return verify(t)
        fake.verify = record
        def guarded_read(path):
            if Path(path) == self.benchmark/'gold.jsonl':
                self.assertEqual(len(calls), 4)
                self.assertEqual(json.loads((out/'run_manifest.json').read_text())['status'], 'predictions_closed')
            return read_rows(path)
        with patch.object(module, 'read_rows', side_effect=guarded_read):
            m = run_verification(self.benchmark, out, mode='codex', verifier=fake, workers=2)
        self.assertEqual(m['comparisons']['verifier']['accuracy'], 1)
        self.assertEqual(file_sha(self.benchmark/'gold.jsonl'), original)
        self.assertTrue((out/'report.html').is_file())
        self.assertIn('INVENTED', (out/'report.html').read_text())
        with self.assertRaisesRegex(ValueError, 'immutable'):
            run_verification(self.benchmark, out, mode='codex', verifier=fake)
        self.assertEqual(len(calls), 4)

    def test_failures_are_cases_and_tampering_blocks_rescoring(self):
        fake = self.fake_verifier()
        fake.verify = lambda t: (_ for _ in ()).throw(OSError('PRIVATE EXCEPTION'))
        out = self.root/'fail'
        m = run_verification(self.benchmark, out, mode='codex', verifier=fake)
        self.assertEqual(m['comparisons']['verifier']['pairs'], 4)
        self.assertEqual(m['comparisons']['verifier']['error_rate'], 1)
        self.assertNotIn('PRIVATE EXCEPTION', ''.join(p.read_text() for p in out.rglob('*.json')))
        rescored = rescore_verification(out, self.root/'rescored')
        self.assertEqual(m, rescored)
        (out/'traces'/'00000.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'trace bytes'): rescore_verification(out, self.root/'tampered')
        self.assertFalse((self.root/'tampered').exists())

    def test_hash_selection_is_gold_independent_and_benchmark_changes_rejected(self):
        fake = self.fake_verifier()
        out = self.root/'pilot'
        run_verification(self.benchmark, out, mode='codex', verifier=fake, limit=2)
        expected = sorted(self.tasks, key=lambda t: digest(t['id']))[:2]
        self.assertEqual(read_rows(out/'inputs.jsonl'), expected)
        (self.benchmark/'inputs.jsonl').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            run_verification(self.benchmark, self.root/'bad', mode='codex', verifier=fake)
        self.assertFalse((self.root/'bad').exists())

    def test_invalid_model_citation_does_not_become_an_assessment(self):
        fake = self.fake_verifier(); verify = fake.verify
        def altered(t):
            trace = verify(t); trace['verdict']['evidence'][0]['quote'] = 'invented alteration'; return trace
        fake.verify = altered
        m = run_verification(self.benchmark, self.root/'invalid', mode='codex', verifier=fake)
        self.assertEqual(m['comparisons']['verifier']['invalid_reference_rate'], 1)
        self.assertEqual(m['comparisons']['verifier']['error_rate'], 1)


if __name__ == '__main__': unittest.main()
