"""Aggregate-publication checks using invented cases only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest
from test_mechanistic_score import fixture, seal
from tools.mechanistic_review.score import score_predictions
from tools.mechanistic_review.publish import make_aggregate, render_html, run


def publication_fixture():
    cases, labels, native, model, protocol_sha, source_sha = fixture()
    report, _ = score_predictions(cases, labels, native, model,
        protocol_sha256=protocol_sha, source_cases_sha256=source_sha)
    report.update(input_files_sha256={'protocol': protocol_sha, 'source_cases': source_sha,
        'labels': '3' * 64, 'native_predictions': '4' * 64, 'model_predictions': '5' * 64},
        scorer_sha256='6' * 64)
    seal(report)
    protocol = {'input_files_sha256': {'source_cases': source_sha, 'labels': '3' * 64},
                'scoring': {'code': {'sha256': '6' * 64}}}
    return report, native, model, protocol, protocol_sha


def aggregate(data):
    report, native, model, protocol, protocol_sha = data
    return make_aggregate(report, native, model, protocol,
        protocol_sha256=protocol_sha, report_sha256='7' * 64,
        native_sha256='4' * 64, model_sha256='5' * 64)


class MechanisticPublishTests(unittest.TestCase):
    def test_all_methods_full_denominators_adverse_outcomes_and_limits(self):
        value = aggregate(publication_fixture())
        self.assertEqual(len(value['methods']), 5)
        self.assertEqual(value['methods']['native_counts']['removed_supported'], 1)
        self.assertEqual(value['methods']['nemotron']['abstained'], 1)
        self.assertEqual(value['methods']['nemotron']['coverage'], .75)
        self.assertIn('2/2 curator-supported', value['headline'])
        self.assertEqual(len(value['bootstrap']['comparisons']), 8)
        html = render_html(value)
        self.assertEqual(html.count('<table>'), 3)
        self.assertIn('INDRA fixed source priors', html)
        self.assertIn('Supported excluded', html)
        self.assertIn('whole-Pharos biological accuracy', html)
        self.assertIn('not a newly unseen independent gold set', html)

    def test_uncertain_or_adverse_primary_is_not_called_established_gain(self):
        data = list(publication_fixture())
        row = next(x for x in data[0]['bootstrap']['comparisons']
                   if x['candidate'] == 'nemotron' and x['comparator'] == 'retain_all')
        row['percentile_95_interval'] = [-.1, .5]
        seal(data[0])
        value = aggregate(data)
        self.assertIn('does not establish', value['primary_interpretation'])
        self.assertNotIn('100%', value['headline'])

    def test_private_fields_and_individual_rows_never_copied(self):
        data = list(publication_fixture())
        data[1]['private_case_id'] = 'PRIVATE_CASE_ID_DO_NOT_PUBLISH'
        data[1]['native_result']['private_source_text'] = 'PRIVATE_SENTENCE_DO_NOT_PUBLISH'
        seal(data[1]['native_result']); seal(data[1])
        data[2]['private_path'] = '/private/DO_NOT_PUBLISH'
        data[2]['rows'][0]['trace']['endpoint'] = 'https://DO_NOT_PUBLISH.invalid'
        seal(data[2])
        data[0].update(native_prediction_seal=data[1]['content_sha256'],
                       model_prediction_seal=data[2]['content_sha256']); seal(data[0])
        value = aggregate(data)
        text = json.dumps(value) + render_html(value)
        self.assertNotIn('DO_NOT_PUBLISH', text)
        self.assertNotIn('native_features', text)
        self.assertNotIn('input_bindings', text)
        self.assertTrue(value['privacy']['aggregate_only'])

    def test_html_escapes_all_dynamic_text(self):
        value = aggregate(publication_fixture())
        value['headline'] = '<script>malicious()</script>'
        value['limitations'].append('<img src=x onerror=alert(1)>')
        html = render_html(value)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img ', html)
        self.assertIn('&lt;script&gt;', html)

    def test_wrong_denominators_removed_arm_or_bad_seal_rejected(self):
        for kind in ('denominator', 'missing_arm', 'seal', 'native_pin', 'metric'):
            data = list(publication_fixture())
            if kind == 'denominator':
                data[0]['methods']['nemotron']['claims'] -= 1; seal(data[0])
            elif kind == 'missing_arm':
                del data[0]['methods']['native_simple']; seal(data[0])
            elif kind == 'seal': data[2]['extra'] = 'tamper'
            elif kind == 'native_pin': data[0]['input_files_sha256']['native_predictions'] = 'f' * 64; seal(data[0])
            else: data[0]['methods']['native_counts']['coverage'] = .1; seal(data[0])
            with self.subTest(kind=kind), self.assertRaises(ValueError): aggregate(data)

    def test_cli_new_output_and_inputs_preserved(self):
        report, native, model, protocol, _ = publication_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            paths = {name: folder / (name + '.json') for name in ('report', 'native', 'model', 'protocol')}
            paths['protocol'].write_text(json.dumps(protocol))
            sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            protocol_sha = sha(paths['protocol'])
            for artifact in (native, model): artifact['protocol_sha256'] = protocol_sha; seal(artifact)
            paths['native'].write_text(json.dumps(native)); paths['model'].write_text(json.dumps(model))
            report.update(protocol_sha256=protocol_sha, native_prediction_seal=native['content_sha256'],
                          model_prediction_seal=model['content_sha256'])
            report['input_files_sha256'].update(protocol=protocol_sha,
                native_predictions=sha(paths['native']), model_predictions=sha(paths['model']))
            seal(report); paths['report'].write_text(json.dumps(report))
            before = {name: sha(path) for name, path in paths.items()}
            output = folder / 'publication'
            result = run(paths['report'], paths['native'], paths['model'], paths['protocol'], protocol_sha, output)
            self.assertTrue(result['all_inputs_unchanged'])
            self.assertEqual(set(result['files']), {'README.md', 'report.html', 'aggregate.json'})
            self.assertEqual(before, {name: sha(path) for name, path in paths.items()})
            with self.assertRaisesRegex(ValueError, 'must be new'):
                run(paths['report'], paths['native'], paths['model'], paths['protocol'], protocol_sha, output)


if __name__ == '__main__':
    unittest.main()
