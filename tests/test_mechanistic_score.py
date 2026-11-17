"""Invented source-faithfulness fixtures; no released cases or predictions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest
from tools.mechanistic_review.model_review import request_for
from tools.mechanistic_review.score import (
    METHODS, metrics, paired_group_bootstrap, run, score_predictions,
)


def seal(value):
    value.pop('content_sha256', None)
    value['content_sha256'] = digest(value)
    return value


def source_case(identifier, split, group, *, complex_claim=False):
    statement = {'type': 'Complex' if complex_claim else 'Activation',
                 'evidence': [{'source_api': 'reach', 'source_hash': 123,
                               'text': 'Invented evidence only.'}]}
    if complex_claim:
        statement['members'] = [
            {'name': 'A', 'db_refs': {}, 'mods': [{'mod_type': 'phosphorylation', 'position': '3'}]},
            {'name': 'B', 'db_refs': {}}, {'name': 'C', 'db_refs': {}}]
    else:
        statement.update(subj={'name': identifier, 'db_refs': {}},
                         obj={'name': identifier + '_TARGET', 'db_refs': {}})
    encoded = json.dumps(statement, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':')).encode()
    return {'case_id': identifier, 'split': split, 'group_id': group,
            'statement': statement, 'input_sha256': hashlib.sha256(encoded).hexdigest(),
            'source_counts': {'reach': 1}, 'original_evidence_count': 1,
            'all_original_evidence_admitted': True}


def fixture():
    cases = [source_case('d1', 'development', 'dev1'), source_case('d2', 'development', 'dev2'),
             source_case('t1', 'test', 'a', complex_claim=True), source_case('t2', 'test', 'a'),
             source_case('t3', 'test', 'b'), source_case('t4', 'test', 'b')]
    labels = [{'case_id': case['case_id'],
               'gold': 'supported' if case['case_id'] in ('d1', 't1', 't3') else 'unsupported',
               'all_original_evidence_curator_reviewed': True} for case in cases]
    reserve = {c['case_id']: c for c in cases if c['split'] == 'test'}

    def native_row(identifier, prune=False):
        return {'case_id': identifier, 'review_proposal': 'prune_candidate' if prune else 'retain_candidate',
                'status': 'scored', 'probability_supported': .2 if prune else .8,
                'source_counts': {'reach': 1}, 'original_evidence_count': 1}

    baseline = seal({'development': [{'case_id': 'd1'}, {'case_id': 'd2'}],
        'reserve': [native_row(i, i in ('t2', 't3')) for i in reserve],
        'simple_prior_comparator': {'threshold': .5, 'released_belief_used': False,
                                   'reserve': [native_row(i) for i in reserve]},
        'source_inputs_unchanged': True, 'graph_changes': 0, 'proposals_applied': False,
        'model': {'fit_split': 'DEV_only', 'threshold': .5},
        'feature_policy': {'reserve_labels_used': False, 'released_belief_used': False}})
    protocol_sha, source_sha = '1' * 64, '2' * 64
    common = {'protocol_sha256': protocol_sha, 'source_cases_sha256': source_sha,
              'input_bindings': {i: c['input_sha256'] for i, c in reserve.items()}}
    native = seal({**common, 'native_result': baseline})
    rows = []
    for identifier, case in reserve.items():
        prompt, schema, _ = request_for(case)
        verdict = 'fails' if identifier in ('t2', 't4') else ('unclear' if identifier == 't1' else 'supports')
        reason = {'fails': 'wrong_relation', 'supports': 'none', 'unclear': 'unclear'}[verdict]
        rows.append(seal({'case_id': identifier, 'input_sha256': case['input_sha256'],
            'status': 'completed', 'proposal': {'fails': 'prune_candidate', 'supports': 'retain_candidate', 'unclear': 'abstain'}[verdict],
            'prompt_sha256': digest(prompt), 'schema_sha256': digest(schema),
            'trace': {'status': 'completed', 'input_sha256': case['input_sha256'],
                      'schema_sha256': digest(schema), 'output': {'E01': {'verdict': verdict, 'reason': reason}}}}))
    model = seal({**common, 'rows': rows})
    return cases, labels, native, model, protocol_sha, source_sha


class MechanisticScoreTests(unittest.TestCase):
    def score(self, data=None):
        cases, labels, native, model, protocol_sha, source_sha = data or fixture()
        return score_predictions(cases, labels, native, model,
                                 protocol_sha256=protocol_sha, source_cases_sha256=source_sha)

    def test_full_denominators_retained_abstentions_and_consensus(self):
        result, methods = self.score()
        self.assertEqual(tuple(result['methods']), METHODS)
        model = result['methods']['nemotron']
        self.assertEqual((model['removed_unsupported'], model['removed_supported']), (2, 0))
        self.assertEqual((model['remaining'], model['abstained']), (2, 1))
        self.assertEqual(model['coverage'], .75)
        self.assertEqual(model['pruning_precision'], 1.)
        self.assertEqual(model['gold_supported_retention_fraction'], 1.)
        self.assertEqual(model['effective_retention_policy_reference_accuracy'], 1.)
        self.assertEqual(result['methods']['retain_all']['effective_retention_policy_reference_accuracy'], .5)
        self.assertEqual(result['methods']['native_counts']['removed_supported'], 1)
        self.assertEqual(result['methods']['consensus']['removed'], 1)
        self.assertEqual(result['methods']['consensus']['retained_graph_supported_precision'], 2 / 3)
        self.assertEqual(methods['consensus']['t1']['proposal'], 'abstain')
        self.assertIsNone(result['methods']['native_simple']['pruning_precision'])
        self.assertFalse(result['policy']['whole_graph_biological_accuracy_claim'])

    def test_failures_abstain_and_context_abstention_has_no_transport(self):
        data = list(fixture())
        row = data[3]['rows'][0]
        row.update(status='context_abstain', proposal='abstain', trace=None)
        seal(row); seal(data[3])
        result, _ = self.score(data)
        self.assertEqual(result['methods']['nemotron']['remaining'], 2)
        row['proposal'] = 'prune_candidate'; seal(row); seal(data[3])
        with self.assertRaisesRegex(ValueError, 'must abstain'):
            self.score(data)

    def test_complete_output_aggregation_and_source_binding_checked(self):
        for tamper in ('output', 'input', 'row_seal', 'envelope_seal', 'missing_case'):
            data = list(fixture())
            row = data[3]['rows'][1]
            if tamper == 'output':
                row['trace']['output'] = {}; seal(row); seal(data[3])
            elif tamper == 'input':
                row['input_sha256'] = 'f' * 64; seal(row); seal(data[3])
            elif tamper == 'row_seal':
                row['proposal'] = 'abstain'; seal(data[3])
            elif tamper == 'envelope_seal':
                data[3]['extra'] = 1
            else:
                data[3]['rows'].pop(); seal(data[3])
            with self.subTest(tamper=tamper), self.assertRaises(ValueError):
                self.score(data)

    def test_no_unknown_false_labels_duplicate_cases_or_cross_split_groups(self):
        for tamper in ('label', 'duplicate', 'group', 'belief', 'evidence', 'threshold'):
            data = list(fixture())
            if tamper == 'label': data[1][0]['gold'] = 'unknown'
            elif tamper == 'duplicate': data[0].append(deepcopy(data[0][0]))
            elif tamper == 'group': data[0][-1]['group_id'] = data[0][0]['group_id']
            elif tamper == 'belief': data[0][-1]['statement']['belief'] = 1.
            elif tamper == 'evidence': data[2]['native_result']['reserve'][0]['source_counts'] = {}; seal(data[2]['native_result']); seal(data[2])
            else: data[2]['native_result']['model']['threshold'] = .9; seal(data[2]['native_result']); seal(data[2])
            with self.subTest(tamper=tamper), self.assertRaises(ValueError):
                self.score(data)

    def test_bootstrap_uses_whole_groups_and_reports_undefined_graphs(self):
        cases, labels, _, _, _, _ = fixture()
        reserve = {r['case_id']: r for r in cases if r['split'] == 'test'}
        gold = {r['case_id']: r['gold'] for r in labels if r['case_id'] in reserve}
        for key in reserve: reserve[key]['group_id'] = 'supported' if gold[key] == 'supported' else 'unsupported'
        retain = {i: {'proposal': 'retain_candidate'} for i in reserve}
        perfect = {i: {'proposal': 'retain_candidate' if gold[i] == 'supported' else 'prune_candidate'} for i in reserve}
        methods = {name: deepcopy(perfect if name == 'nemotron' else retain) for name in METHODS}
        result = paired_group_bootstrap(reserve, gold, methods)
        comparison = next(r for r in result['comparisons'] if r['candidate'] == 'nemotron' and r['comparator'] == 'retain_all')
        # Two whole groups: sampling only the unsupported group occurs ~1/4,
        # unlike independent record resampling (~1/16). Empty graphs stay null.
        self.assertGreater(comparison['undefined_paired_draws'], 2300)
        self.assertLess(comparison['undefined_paired_draws'], 2700)
        self.assertEqual(comparison['percentile_95_interval'], [0., .5])
        self.assertIn('conditional', comparison['interval_scope'])
        again = paired_group_bootstrap(reserve, gold, methods)
        self.assertEqual(result, again)
        for case in reserve.values(): case['group_id'] = 'one'
        self.assertEqual(paired_group_bootstrap(reserve, gold, methods)['status'], 'unavailable_fewer_than_two_groups')

    def test_zero_denominators_are_null(self):
        result = metrics({'x': 'unsupported'}, {'x': {'proposal': 'prune_candidate'}})
        self.assertIsNone(result['retained_graph_supported_precision'])
        self.assertIsNone(result['gold_supported_retention_fraction'])
        self.assertIsNone(result['effective_retention_policy_balanced_accuracy'])

    def test_cli_contract_frozen_pins_and_typed_reference_views(self):
        cases, labels, native, model, _, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            case_path, label_path = folder / 'cases.jsonl', folder / 'labels.jsonl'
            for path, rows in ((case_path, cases), (label_path, labels)):
                path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            code = Path(__file__).resolve().parents[1] / 'tools/mechanistic_review/score.py'
            protocol = {'input_files_sha256': {'source_cases': sha(case_path), 'labels': sha(label_path)},
                        'scoring': {'bootstrap_replicates': 10000, 'seed': 20261117,
                                    'code': {'file': str(code), 'sha256': sha(code)}}}
            protocol_path = folder / 'protocol.json'; protocol_path.write_text(json.dumps(protocol))
            for artifact in (native, model):
                artifact.update(protocol_sha256=sha(protocol_path), source_cases_sha256=sha(case_path)); seal(artifact)
            native_path, model_path = folder / 'native.json', folder / 'model.json'
            native_path.write_text(json.dumps(native)); model_path.write_text(json.dumps(model))
            output = folder / 'assessment'
            result = run(protocol_path, sha(protocol_path), case_path, label_path,
                         native_path, model_path, output)
            self.assertTrue(result['all_frozen_inputs_unchanged'])
            self.assertEqual(len(result['reference_view_files']), 10)
            graph = json.loads((output / 'nemotron/retained_reference_graph.json').read_text())
            self.assertEqual(graph['statement_case_ids'], ['t1', 't3'])
            self.assertEqual(graph['statements'][0], cases[2]['statement'])
            self.assertEqual(len(graph['statements'][0]['members']), 3)
            self.assertEqual(graph['statements'][0]['members'][0]['mods'][0]['position'], '3')
            self.assertEqual(len((output / 'nemotron/dispositions.jsonl').read_text().splitlines()), 4)
            with self.assertRaisesRegex(ValueError, 'must be new'):
                run(protocol_path, sha(protocol_path), case_path, label_path, native_path, model_path, output)
            label_path.write_text(label_path.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'frozen protocol pins'):
                run(protocol_path, sha(protocol_path), case_path, label_path, native_path, model_path, folder / 'changed')


if __name__ == '__main__':
    unittest.main()
