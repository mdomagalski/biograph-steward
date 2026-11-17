"""Invented native-INDRA fixtures; no real curator cases or network requests."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.mechanistic_review.native_baseline import (
    PARAMETERS, fit_predict_native, run_frozen_protocol,
)


AVAILABLE = bool(importlib.util.find_spec('indra') and importlib.util.find_spec('sklearn'))


@unittest.skipUnless(AVAILABLE, 'optional qualified INDRA/sklearn runtime required')
class NativeBaselineTests(unittest.TestCase):
    def setUp(self):
        from indra.statements import Activation, Agent, Evidence

        class NoBeliefActivation(Activation):
            def __getattribute__(self, name):
                if name == 'belief':
                    raise AssertionError('Released belief was accessed.')
                return super().__getattribute__(name)

        def statement(name, source, count, *, annotation=None):
            return NoBeliefActivation(Agent(name), Agent(name + '_TARGET'), evidence=[
                Evidence(source_api=source, source_id=str(i), text='Invented evidence.',
                         annotations=annotation or {}) for i in range(count)])
        self.statement = statement
        self.dev = [statement('D1', 'reach', 8), statement('D2', 'sparser', 8),
                    statement('D3', 'reach', 6), statement('D4', 'sparser', 6)]
        self.ids = ['d1', 'd2', 'd3', 'd4']
        self.labels = {'d3': 1, 'd2': 0, 'd4': 0, 'd1': 1}
        self.reserve = [statement('R1', 'reach', 7), statement('R2', 'sparser', 7)]

    def run_baseline(self, **kwargs):
        return fit_predict_native(self.dev, self.labels, self.ids,
                                  self.reserve, ['r1', 'r2'], **kwargs)

    def test_native_features_order_complete_evidence_and_no_belief(self):
        result = self.run_baseline()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['feature_policy']['source_list'], ['reach', 'sparser'])
        self.assertEqual([r['native_features'] for r in result['development']],
                         [[8., 0.], [0., 8.], [6., 0.], [0., 6.]])
        self.assertEqual([r['native_features'] for r in result['reserve']], [[7., 0.], [0., 7.]])
        self.assertEqual([r['review_proposal'] for r in result['reserve']],
                         ['retain_candidate', 'prune_candidate'])
        self.assertEqual([r['original_evidence_count'] for r in result['reserve']], [7, 7])
        self.assertTrue(result['source_inputs_unchanged'])
        self.assertFalse(result['feature_policy']['released_belief_used'])
        self.assertFalse(result['simple_prior_comparator']['released_belief_used'])
        self.assertEqual(result['graph_changes'], 0)
        json.dumps(result, allow_nan=False)

    def test_label_map_is_joined_by_id_and_fit_receives_DEV_only(self):
        from sklearn.linear_model import LogisticRegression
        original = LogisticRegression.fit
        seen = []

        def record(model, matrix, labels, *args, **kwargs):
            seen.append((matrix.tolist(), list(labels)))
            return original(model, matrix, labels, *args, **kwargs)

        with patch.object(LogisticRegression, 'fit', record):
            self.run_baseline(include_simple=False)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][1], [1, 0, 1, 0])
        self.assertEqual(len(seen[0][0]), 4)
        bad = {**self.labels, 'r1': 1}
        with self.assertRaisesRegex(ValueError, 'exactly DEV IDs'):
            fit_predict_native(self.dev, bad, self.ids, self.reserve, ['r1', 'r2'])

    def test_reserve_annotations_and_order_are_not_training_features(self):
        result = self.run_baseline(include_simple=False)
        changed = [self.statement('R2', 'sparser', 7, annotation={'correct': True}),
                   self.statement('R1', 'reach', 7, annotation={'incorrect': True})]
        again = fit_predict_native(self.dev, self.labels, self.ids, changed,
                                   ['r2', 'r1'], include_simple=False)
        left = {r['case_id']: r['probability_supported'] for r in result['reserve']}
        right = {r['case_id']: r['probability_supported'] for r in again['reserve']}
        self.assertEqual(left, right)
        self.assertEqual(result['model']['coefficients'], again['model']['coefficients'])

    def test_id_or_native_claim_overlap_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'IDs overlap'):
            fit_predict_native(self.dev, self.labels, self.ids, self.reserve, ['d1', 'r2'])
        with self.assertRaisesRegex(ValueError, 'native claims overlap'):
            fit_predict_native(self.dev, self.labels, self.ids,
                               [self.statement('D1', 'reach', 1)], ['different_id'])

    def test_unknown_labels_are_not_converted_to_negatives(self):
        for value in (None, 'unsupported', False):
            labels = {**self.labels, 'd2': value}
            with self.assertRaisesRegex(ValueError, 'explicit integer labels'):
                fit_predict_native(self.dev, labels, self.ids, self.reserve, ['r1', 'r2'])

    def test_new_source_abstains_without_dropping_its_evidence(self):
        reserve = [self.statement('NEW', 'unseen_source', 4)]
        result = fit_predict_native(self.dev, self.labels, self.ids, reserve, ['new'])
        row = result['reserve'][0]
        self.assertEqual(row['status'], 'abstain')
        self.assertIsNone(row['probability_supported'])
        self.assertIsNone(row['prediction'])
        self.assertIsNone(row['native_features'])
        self.assertEqual(row['source_counts'], {'unseen_source': 4})
        self.assertEqual(result['feature_policy']['source_list'], ['reach', 'sparser'])
        self.assertEqual(result['simple_prior_comparator']['reserve'][0]['status'], 'abstain')

    def test_native_model_failure_abstains_without_fallback(self):
        from sklearn.linear_model import LogisticRegression
        with patch.object(LogisticRegression, 'fit', side_effect=RuntimeError('invented fit error')):
            result = self.run_baseline()
        self.assertEqual(result['status'], 'abstained_model_error')
        self.assertTrue(all(r['status'] == 'abstain' and r['prediction'] is None
                            and r['probability_supported'] is None for r in result['reserve']))
        self.assertTrue(all(r['status'] == 'scored'
                            for r in result['simple_prior_comparator']['reserve']))

    def protocol_fixture(self, folder):
        from indra.statements import Activation, Agent, Evidence
        rows = []
        for identifier, split, source, count in [
                ('d1', 'development', 'reach', 8), ('d2', 'development', 'sparser', 8),
                ('d3', 'development', 'reach', 6), ('d4', 'development', 'sparser', 6),
                ('r1', 'test', 'reach', 7), ('r2', 'test', 'sparser', 7)]:
            statement = Activation(Agent(identifier), Agent(identifier + '_TARGET'),
                                   evidence=[Evidence(source_api=source) for _ in range(count)])
            native = statement.to_json()
            native.pop('belief')
            row = {'case_id': identifier, 'group_id': identifier + '_group',
                   'split': split, 'statement': native, 'source_counts': {source: count}}
            row['input_sha256'] = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
            rows.append(row)
        cases = folder / 'source_cases.jsonl'
        cases.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        labels = folder / 'development_labels.jsonl'
        labels.write_text(''.join(json.dumps({'case_id': identifier,
                          'gold': 'supported' if label else 'unsupported'}) + '\n'
                          for identifier, label in self.labels.items()))
        from tools.mechanistic_review import native_baseline

        def pin(path):
            return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

        protocol = folder / 'protocol.json'
        config = {'native_baseline': {'source_cases': pin(cases),
                  'development_labels': pin(labels), 'code': pin(Path(native_baseline.__file__)),
                  'development_count': 4, 'reserve_count': 2, 'parameters': PARAMETERS,
                  'include_simple': True},
                  # Deliberately nonexistent: the native CLI must never open this.
                  'reserve_labels_for_later_scoring': {'file': str(folder / 'DO_NOT_OPEN')}}
        protocol.write_text(json.dumps(config))
        return protocol, pin(protocol)['sha256'], cases, labels, rows

    def test_frozen_CLI_writes_source_bound_envelope_without_reserve_labels(self):
        with tempfile.TemporaryDirectory(prefix='biograph-native-fixture-') as name:
            folder = Path(name).resolve()
            protocol, pin, cases, labels, rows = self.protocol_fixture(folder)
            before = {p.name: p.read_bytes() for p in (protocol, cases, labels)}
            command = [sys.executable, '-m', 'tools.mechanistic_review.native_baseline',
                       '--protocol', str(protocol), '--protocol-sha256', pin,
                       '--source-cases', str(cases), '--dev-labels', str(labels),
                       '--out', str(folder / 'output')]
            ran = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                 check=True, capture_output=True, text=True)
            summary = json.loads(ran.stdout)
            self.assertEqual(summary['status'], 'completed')
            self.assertFalse(summary['reserve_label_file_opened'])
            envelope = json.loads((folder / 'output/native_results.json').read_text())
            self.assertEqual(envelope['protocol_sha256'], pin)
            self.assertEqual(envelope['input_bindings'],
                             {r['case_id']: r['input_sha256'] for r in rows if r['split'] == 'test'})
            self.assertEqual({r['case_id'] for r in envelope['native_result']['reserve']}, {'r1', 'r2'})
            self.assertEqual(before, {p.name: p.read_bytes() for p in (protocol, cases, labels)})
            self.assertFalse((folder / 'DO_NOT_OPEN').exists())

    def test_frozen_CLI_rejects_source_tamper_before_native_model(self):
        with tempfile.TemporaryDirectory(prefix='biograph-native-fixture-') as name:
            folder = Path(name).resolve()
            protocol, pin, cases, labels, _ = self.protocol_fixture(folder)
            cases.write_text(cases.read_text() + '\n')
            with patch('tools.mechanistic_review.native_baseline._runtime',
                       side_effect=AssertionError('must not reach a model')):
                with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
                    run_frozen_protocol(protocol, pin, cases, labels, folder / 'output')
            self.assertFalse((folder / 'output').exists())

    def test_frozen_CLI_rejects_reserve_label_even_with_valid_file_pin(self):
        with tempfile.TemporaryDirectory(prefix='biograph-native-fixture-') as name:
            folder = Path(name).resolve()
            protocol, _, cases, labels, _ = self.protocol_fixture(folder)
            labels.write_text(labels.read_text() + json.dumps({'case_id': 'r1', 'gold': 'supported'}) + '\n')
            config = json.loads(protocol.read_text())
            config['native_baseline']['development_labels']['sha256'] = hashlib.sha256(labels.read_bytes()).hexdigest()
            protocol.write_text(json.dumps(config))
            pin = hashlib.sha256(protocol.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'DEV-only label file'):
                run_frozen_protocol(protocol, pin, cases, labels, folder / 'output')
            self.assertFalse((folder / 'output').exists())


class OptionalImportTests(unittest.TestCase):
    def test_adapter_import_needs_no_optional_packages(self):
        root = Path(__file__).resolve().parents[1]
        code = ('import sys; from tools.mechanistic_review import native_baseline; '
                'assert "indra" not in sys.modules and "sklearn" not in sys.modules')
        subprocess.run([sys.executable, '-S', '-c', code], cwd=root, check=True,
                       capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
